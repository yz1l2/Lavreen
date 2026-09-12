"""
وحدة مساعدة تتواصل مع OpenRouter API لعمل شيئين:
1. extract_filters(): تفهم كلام العميل الحر وتحوله لفلاتر منظمة (JSON)
2. rank_listings(): تاخذ نتائج الفلترة وترتبها حسب الأنسب لطلب العميل مع شرح مختصر

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

    # يدور على أول object { } أو array [ ] كامل بالنص
    match = re.search(r"\{.*\}|\[.*\]", text, re.DOTALL)

    if match:
        text = match.group(0)

    return json.loads(text)


def extract_filters(user_query):
    """
    يرجع dict فيه:
    category, keywords(list), city, min_price, max_price,
    min_year, max_year, max_mileage
    """

    system_prompt = """أنت أداة استخراج بيانات فقط لموقع إعلانات مبوبة سعودي
(سيارات، جوالات، عقار، كمبيوتر، وغيرها).

اقرأ طلب العميل وأرجع JSON فقط بدون أي شرح أو نص إضافي.

استخدم المفاتيح التالية بالضبط:

{
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
        {
            "role": "system",
            "content": system_prompt
        },
        {
            "role": "user",
            "content": user_query
        }
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
        filters = {}

    return filters


def rank_listings(user_query, listings):
    """
    listings:
    list of dicts:
    id, title, price, city, year, mileage...

    يرجع:
    [
        {"id": 3, "reason": "أفضل خيار لأن..."},
        ...
    ]
    """

    if not listings:
        return []

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

    system_prompt = """أنت مساعد مبيعات خبير بموقع إعلانات مبوبة سعودي.

هدفك ترتيب قائمة الإعلانات حسب مدى مناسبتها لطلب العميل.

اشرح باختصار بجملة واحدة لماذا كل إعلان مناسب.

أرجع JSON فقط بهذا الشكل:

[
  {
    "id": 3,
    "reason": "أفضل سعر مع أقل ماشية ضمن الميزانية"
  },
  {
    "id": 1,
    "reason": "خيار جيد لكن السعر أعلى قليلاً"
  }
]

رتب من الأفضل إلى الأقل مناسبة.

لا تضف أي إعلان غير موجود في القائمة المرسلة لك."""

    user_message = f"""طلب العميل:
{user_query}

الإعلانات المتاحة (JSON):
{json.dumps(compact_listings, ensure_ascii=False)}"""

    messages = [
        {
            "role": "system",
            "content": system_prompt
        },
        {
            "role": "user",
            "content": user_message
        }
    ]

    try:
        raw_text = _call_ai(messages, max_tokens=1500)

        ranking = _extract_json_block(raw_text)

    except (
        json.JSONDecodeError,
        AttributeError,
        RuntimeError,
        requests.RequestException,
        KeyError,
        re.error
    ) as e:
        print("RANK_LISTINGS FAILED:", type(e).__name__, str(e))
        try:
            print("RAW MODEL OUTPUT WAS:", raw_text)
        except NameError:
            print("NO RESPONSE RECEIVED FROM OPENROUTER AT ALL")
        ranking = [
            {
                "id": l["id"],
                "reason": ""
            }
            for l in compact_listings
        ]

    return ranking