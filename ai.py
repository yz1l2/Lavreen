import re


def ai_search(query, listings):
    """
    يحلل طلب المستخدم بشكل بسيط
    ويرتب الإعلانات حسب مدى تطابقها.
    """

    text = query.lower()

    # استخراج الميزانية
    budget = None

    numbers = re.findall(r"\d+(?:,\d+)?", text)

    if numbers:
        try:
            budget = float(numbers[-1].replace(",", ""))
        except ValueError:
            pass

    # كلمات مهمة
    keywords = [
        word.strip()
        for word in re.findall(r"[\w\u0600-\u06FF]+", text)
        if len(word.strip()) >= 2
    ]

    results = []

    for listing in listings:

        score = 0

        title = str(listing["title"]).lower()
        category = str(listing["category"]).lower()
        city = str(listing["city"]).lower()
        description = str(listing["description"]).lower()

        full_text = f"{title} {category} {city} {description}"

        # تطابق الكلمات
        for keyword in keywords:
            if keyword in full_text:
                score += 2

        # الميزانية
        if budget is not None:
            price = float(listing["price"])

            if price <= budget:
                score += 5
            else:
                score -= 3

        if score > 0:
            results.append((score, listing))

    # ترتيب الأفضل أولًا
    results.sort(key=lambda item: item[0], reverse=True)

    return [listing for score, listing in results]