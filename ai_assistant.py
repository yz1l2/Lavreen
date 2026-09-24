"""
وحدة مساعدة تتواصل مع OpenRouter API لعمل هذي الأشياء:
1. extract_filters(): تفهم كلام العميل الحر وتحوله لفلاتر منظمة (JSON)
2. respond_with_listings(): ترتب النتائج + تصيغ رد طبيعي متجاوب مع كلام العميل (مو جملة ثابتة)
3. respond_no_results(): رد طبيعي لما ما تكون فيه نتائج مطابقة

تحتاج متغير بيئة OPENROUTER_API_KEY معرّف على الجهاز أو السيرفر.
"""

import os
import json
import re
import requests

MODEL = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini")
API_KEY = os.environ.get("OPENROUTER_API_KEY")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def _call_ai(messages, max_tokens=500):
    """إرسال طلب إلى OpenRouter وإرجاع النص الناتج."""

    if not API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY غير موجود في متغيرات البيئة")

    response = requests.post(
        OPENROUTER_URL,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://lavreen.onrender.com",
            "X-Title": "Lavreen",
        },
        json={
            "model": MODEL,
            "messages": messages,
            "max_tokens": max_tokens,
        },
        timeout=60,
    )

    response.raise_for_status()

    data = response.json()

    return data["choices"][0]["message"]["content"]


def _extract_json_block(text):
    """يحاول سحب أول JSON صالح من رد النموذج."""

    text = text.strip()

    text = re.sub(
        r"^```json\s*|^```\s*|```$",
        "",
        text,
        flags=re.MULTILINE
    ).strip()

    # يدور على أول object { } كامل بالنص
    match = re.search(r"\{.*\}", text, re.DOTALL)

    if match:
        text = match.group(0)

    return json.loads(text)


def extract_filters(user_query):
    """
    يرجع dict فيه:
    is_search (bool), category, keywords(list), city, min_price, max_price,
    min_year, max_year, max_mileage

    لو الرسالة مو طلب بحث فعلي (سلام، شكراً، كلام عادي)، يرجع is_search: false
    """

    system_prompt = """أنت أداة استخراج بيانات فقط لموقع إعلانات مبوبة سعودي
(سيارات، جوالات، عقار، كمبيوتر، وغيرها).

أول شي حدد: هل رسالة العميل فعلاً طلب بحث عن منتج أو إعلان (حتى لو عام زي "أبي شي رخيص")،
أو مجرد كلام عادي/سلام/شكر/سؤال مو متعلق بالبحث؟

لو مو طلب بحث فعلي، أرجع فقط:
{"is_search": false}

لو طلب بحث فعلي، اقرأ الطلب وأرجع JSON بالمفاتيح التالية بالضبط:

{
  "is_search": true,
  "category": "تصنيف الإعلان إن ذكر (سيارات/جوالات/عقار/كمبيوتر) أو null",
  "keywords": ["كلمات مفتاحية مثل الماركة والموديل"],
  "city": "اسم المدينة إن ذكرت أو null",
  "min_price": رقم أو null,
  "max_price": رقم أو null,
  "min_year": رقم أو null,
  "max_year": رقم أو null,
  "max_mileage": رقم أو null
}

لو قال العميل "ميزانية كذا" أو "بحدود كذا" اعتبرها max_price.

لو قال "ماشية قليلة" بدون رقم حدد تقريباً 30000.

لو قال "شبه جديدة" حدد تقريباً 15000.

أرجع JSON صالح فقط، بدون أي نص قبله أو بعده."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_query}
    ]

    try:
        raw_text = _call_ai(messages, max_tokens=500)
        filters = _extract_json_block(raw_text)

    except (json.JSONDecodeError, AttributeError, RuntimeError, requests.RequestException, KeyError, re.error) as e:
        print("EXTRACT_FILTERS FAILED:", type(e).__name__, str(e))
        try:
            print("RAW MODEL OUTPUT WAS:", raw_text)
        except NameError:
            print("NO RESPONSE RECEIVED FROM OPENROUTER AT ALL")
        # عند أي فشل تقني، نعتبرها مو طلب بحث بدل ما نطلع كل المنتجات بالغلط
        filters = {"is_search": False}

    return filters


def respond_with_listings(user_query, listings):
    """
    listings: list of dicts (id, title, price, city, year, mileage...)

    يرجع dict:
    {
        "reply": "رد طبيعي متجاوب مع كلام العميل، جملة أو جملتين",
        "items": [{"id": 3, "reason": "أفضل سعر..."}, ...]   # مرتبة من الأفضل للأقل
    }
    """

    if not listings:
        return {"reply": "", "items": []}

    compact_listings = [
        {
            "id": l["id"],
            "title": l["title"],
            "price": l["price"],
            "city": l["city"],
            "year": l.get("year"),
            "mileage": l.get("mileage"),
        }
        for l in listings
    ]

    system_prompt = """أنت مساعد مبيعات ودود وخبير بموقع إعلانات مبوبة سعودي اسمه لافرين، تتكلم باللهجة السعودية بأسلوب طبيعي كأنك موظف حقيقي يرد على عميل بالشات.

مهمتك:
1. تكتب رد قصير طبيعي (جملة أو جملتين بس) يتفاعل مع طلب العميل تحديداً - مثلاً يذكر الميزانية أو الماركة أو المدينة اللي طلبها، ويعطيه إحساس إنك فهمت طلبه بالضبط. لا تكرر نفس الجملة الجاهزة كل مرة، نوّع بالصياغة.
2. ترتب الإعلانات المرسلة لك من الأفضل للأقل مناسبة لطلبه، مع سبب مختصر (جملة وحدة) لكل واحد.

أرجع JSON فقط بهذا الشكل بالضبط، بدون أي نص قبله أو بعده:

{
  "reply": "الرد الطبيعي هنا",
  "items": [
    {"id": 3, "reason": "أفضل سعر مع أقل ماشية ضمن ميزانيتك"},
    {"id": 1, "reason": "خيار جيد لكن السعر أعلى شوي"}
  ]
}

لا تضف أي إعلان غير موجود في القائمة المرسلة لك."""

    user_message = f"""طلب العميل:
{user_query}

الإعلانات المتاحة (JSON):
{json.dumps(compact_listings, ensure_ascii=False)}"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ]

    try:
        raw_text = _call_ai(messages, max_tokens=1500)
        result = _extract_json_block(raw_text)

        if not isinstance(result, dict) or "items" not in result:
            raise ValueError("شكل الرد غير متوقع")

        result.setdefault("reply", f"لقيت لك {len(compact_listings)} إعلان يطابق طلبك:")
        return result

    except (json.JSONDecodeError, AttributeError, RuntimeError, requests.RequestException, KeyError, re.error, ValueError) as e:
        print("RESPOND_WITH_LISTINGS FAILED:", type(e).__name__, str(e))
        try:
            print("RAW MODEL OUTPUT WAS:", raw_text)
        except NameError:
            print("NO RESPONSE RECEIVED FROM OPENROUTER AT ALL")
        return {
            "reply": f"لقيت لك {len(compact_listings)} إعلان يطابق طلبك:",
            "items": [{"id": l["id"], "reason": ""} for l in compact_listings],
        }


def respond_general(user_query):
    """رد طبيعي على كلام عادي مو طلب بحث (سلام، شكراً، أسئلة عامة)."""

    system_prompt = """أنت مساعد ودود بموقع إعلانات مبوبة سعودي اسمه لافرين، تتكلم باللهجة السعودية.
العميل كتب رسالة مو طلب بحث عن منتج (سلام، شكر، سؤال عام...).
رد عليه بشكل طبيعي وودود بجملة أو جملتين، ولو مناسب اسأله وش يدور عليه بالضبط عشان تساعده.
أرجع نص عادي بس، بدون أي تنسيق JSON أو علامات اقتباس."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_query}
    ]

    try:
        raw_text = _call_ai(messages, max_tokens=200)
        return raw_text.strip().strip('"')
    except (RuntimeError, requests.RequestException) as e:
        print("RESPOND_GENERAL FAILED:", type(e).__name__, str(e))
        return "أهلاً فيك! وش تدور عليه اليوم؟ 😊"


def respond_no_results(user_query):
    """رد طبيعي ودود لما ما تكون فيه نتائج مطابقة للطلب."""

    system_prompt = """أنت مساعد مبيعات ودود بموقع إعلانات مبوبة سعودي اسمه لافرين، تتكلم باللهجة السعودية.
العميل طلب شي وما فيه أي إعلان يطابق طلبه حالياً بالموقع.
اكتب رد قصير ودود (جملة أو جملتين) يوضح له إنه ما فيه نتائج، ويقترح عليه يخفف شرط أو اثنين (زي الميزانية أو السنة أو المدينة) بدون ما تخترع تفاصيل مو موجودة بطلبه.
أرجع نص عادي بس، بدون أي تنسيق JSON أو علامات اقتباس."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"طلب العميل: {user_query}"}
    ]

    try:
        raw_text = _call_ai(messages, max_tokens=200)
        return raw_text.strip().strip('"')
    except (RuntimeError, requests.RequestException) as e:
        print("RESPOND_NO_RESULTS FAILED:", type(e).__name__, str(e))
        return "ما لقيت إعلانات تطابق طلبك بالضبط، جرب تخفف الشروط شوي (زي الميزانية أو السنة)."