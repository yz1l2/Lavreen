"""
وحدة مساعدة تتواصل مع OpenRouter API لعمل هذي الأشياء:
1. extract_filters(): تفهم كلام العميل الحر وتحدد هل هو طلب بحث أو كلام عادي، وتستخرج فلاتر منظمة
2. respond_with_listings(): ترتب النتائج + تصيغ رد طبيعي متجاوب مع كلام العميل
3. respond_general(): رد طبيعي على كلام عادي (سلام، شكراً...)
4. respond_no_results(): رد طبيعي لما ما تكون فيه نتائج مطابقة

تحتاج متغير بيئة OPENROUTER_API_KEY معرّف على الجهاز أو السيرفر.

ملاحظة عن النماذج المجانية: تتغير وتنقطع بدون سابق إنذار بـ OpenRouter، فالكود يجرب
عدة نماذج بالترتيب تلقائياً (FALLBACK_MODELS)، وآخرهم "openrouter/free" كحل مضمون دايماً.

ملاحظة عن الأخطاء: أي فشل نهائي بالاتصال يطلع نصه الحقيقي مباشرة برد الشات نفسه
(مسبوق بـ ⚠️) عشان تقدر تشخص المشكلة من الموقع مباشرة بدون سجلات Render.
"""

import os
import json
import re
import requests

MODEL = os.environ.get("OPENROUTER_MODEL", "meta-llama/llama-4-maverick:free")

# لو النموذج الأساسي فشل أو انقطع (شي شائع بالنماذج المجانية)، نجرب هذي بالترتيب تلقائياً
FALLBACK_MODELS = [
    "qwen/qwen3-coder:free",
    "deepseek/deepseek-chat-v3.1:free",
    "openrouter/free",  # حل أخير مضمون: راوتر يختار أي نموذج مجاني متوفر حالياً
]

API_KEY = os.environ.get("OPENROUTER_API_KEY")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


class AIError(Exception):
    """خطأ واضح يحمل تفاصيل حقيقية عن سبب فشل الاتصال بـ OpenRouter (بعد تجربة كل النماذج)."""
    pass


def _try_one_model(model_name, messages, max_tokens):
    """يرسل طلب واحد لنموذج معين. يرفع استثناء عادي عند الفشل (يُلتقط من _call_ai)."""

    response = requests.post(
        OPENROUTER_URL,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://lavreen.onrender.com",
            "X-Title": "Lavreen",
        },
        json={
            "model": model_name,
            "messages": messages,
            "max_tokens": max_tokens,
        },
        timeout=60,
    )

    if response.status_code != 200:
        raise ValueError(f"HTTP {response.status_code}: {response.text[:300]}")

    data = response.json()
    return data["choices"][0]["message"]["content"]


def _call_ai(messages, max_tokens=500):
    """
    يرسل الطلب للنموذج الأساسي، ولو فشل يجرب النماذج البديلة بالترتيب.
    يرجع النص الناتج من أول نموذج ينجح. لو الكل فشل، يرفع AIError بتفاصيل آخر خطأ.
    """

    if not API_KEY:
        raise AIError("مفتاح OPENROUTER_API_KEY غير موجود في متغيرات البيئة بـ Render")

    models_to_try = [MODEL] + [m for m in FALLBACK_MODELS if m != MODEL]
    last_error = None

    for model_name in models_to_try:
        try:
            return _try_one_model(model_name, messages, max_tokens)
        except requests.RequestException as e:
            last_error = f"{model_name} → فشل الاتصال: {type(e).__name__}: {e}"
            print("MODEL FAILED:", last_error)
            continue
        except (ValueError, KeyError, IndexError, json.JSONDecodeError) as e:
            last_error = f"{model_name} → {e}"
            print("MODEL FAILED:", last_error)
            continue

    raise AIError(f"كل النماذج فشلت. آخر خطأ: {last_error}")


def _extract_json_block(text):
    """يحاول سحب أول JSON صالح من رد النموذج."""

    text = text.strip()

    text = re.sub(
        r"^```json\s*|^```\s*|```$",
        "",
        text,
        flags=re.MULTILINE
    ).strip()

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
    لو صار خطأ تقني، يرجع is_search: false + مفتاح _error فيه تفاصيل الخطأ الحقيقية
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
        return filters

    except AIError as e:
        print("EXTRACT_FILTERS FAILED (AIError):", str(e))
        return {"is_search": False, "_error": str(e)}

    except (json.JSONDecodeError, AttributeError, KeyError, re.error) as e:
        print("EXTRACT_FILTERS FAILED (parse):", type(e).__name__, str(e))
        print("RAW MODEL OUTPUT WAS:", raw_text)
        return {"is_search": False, "_error": f"رد النموذج ما كان JSON صالح: {raw_text[:200]}"}


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
            raise ValueError("شكل الرد غير متوقع من النموذج")

        result.setdefault("reply", f"لقيت لك {len(compact_listings)} إعلان يطابق طلبك:")
        return result

    except AIError as e:
        print("RESPOND_WITH_LISTINGS FAILED (AIError):", str(e))
        return {
            "reply": f"⚠️ تعذر الاتصال بالذكاء الاصطناعي: {e}",
            "items": [{"id": l["id"], "reason": ""} for l in compact_listings],
        }

    except (json.JSONDecodeError, AttributeError, KeyError, re.error, ValueError) as e:
        print("RESPOND_WITH_LISTINGS FAILED (parse):", type(e).__name__, str(e))
        print("RAW MODEL OUTPUT WAS:", raw_text)
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
    except AIError as e:
        print("RESPOND_GENERAL FAILED (AIError):", str(e))
        return f"⚠️ تعذر الاتصال بالذكاء الاصطناعي: {e}"


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
    except AIError as e:
        print("RESPOND_NO_RESULTS FAILED (AIError):", str(e))
        return "ما لقيت إعلانات تطابق طلبك بالضبط، جرب تخفف الشروط شوي (زي الميزانية أو السنة)."