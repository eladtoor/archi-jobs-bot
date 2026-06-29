"""Classifier recall/precision tests — the heart of 'never miss'."""

import pytest

from arch_job_bot.matching.classifier import classify

ACCEPT = [
    "דרוש/ה אדריכל/ית למשרד אדריכלות מוביל בבאר שבע",
    "הנדסאי/ת אדריכלות לניהול פרויקטים תכנוניים",
    "בודק/ת תכניות במחלקת תכנון עיר בעירייה",
    "דרושים שרטט /ת למשרד אדריכלות מוביל בקריית גת - 15k!",
    "מעצב/ת פנים לסטודיו עיצוב פנים מוביל",
    "דרוש/ה אדריכל/ית נוף לחברה",
    "Landscape Architect for a leading design firm",
    "Urban Planner needed",
    "אדר' רישוי עם ניסיון בהגשת גרמושקה והיתרי בנייה",
    "אדריכל/ית עם ניסיון ב-AutoCAD ו-Revit לפרויקטים",
    # structural co-mention but architect explicitly sought → keep
    "משרד אדריכלים מגייס אדריכל/ית או הנדסאי/ת בניין",
    "דרוש/ה עורך/ת בקשה להיתר ברשות רישוי",
]

REJECT = [
    "דרוש Senior Software Architect with Java, AWS and Kubernetes",
    "אדריכל תוכנה / Software Architect לחברת הייטק",
    "Solution Architect - microservices, Docker, CI/CD",
    "ארכיטקט פתרונות ענן עם ניסיון ב-Azure",
    "דרוש קונסטרוקטור / מהנדס מבנים לחברת בנייה",  # pure structural
    "סוכן נדל\"ן / מתווך דירות למשרד תיווך",          # sales
    "דרוש/ה שרטט/ת חשמל לחברת חשמל ואלקטרוניקה",     # non-arch drafting
    "דרוש/ה מנהל/ת מכירות לחברה",                     # no signal
    "ארכיטקט נתונים Data Architect עם SQL",
]


@pytest.mark.parametrize("text", ACCEPT)
def test_accepts_real_architecture_jobs(text):
    c = classify(text)
    assert c.accepted, f"should ACCEPT but rejected ({c.reason}): {text}"


@pytest.mark.parametrize("text", REJECT)
def test_rejects_non_architecture(text):
    c = classify(text)
    assert not c.accepted, f"should REJECT but accepted: {text}"


def test_software_tokens_alone_not_sufficient():
    # AutoCAD/Revit with no role term must NOT match.
    assert not classify("דרוש/ה עובד/ת עם ידע ב-AutoCAD ו-Revit").accepted


def test_bare_arch_word_with_tech_qualifier_rejected():
    assert not classify("אדריכל תוכנה").accepted
