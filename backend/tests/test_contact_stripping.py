"""Contact details are removed from imported postings (D055)."""
from app.job_sources.text import html_to_text, strip_contact_details


def test_emails_phones_and_named_contacts_are_replaced():
    text = ("Requirements\n- Python\n\n"
            "Questions? Contact Jane Example at jane.example@example.com or +49 30 1234 5678.\n"
            "Recruiter: Max Mustermann\n"
            "Ihre Ansprechpartnerin: Frau Anna Maria Muster, Tel. 030 12345678\n"
            "Heb je vragen? Neem contact op met Sanne de Vries.\n"
            "We look forward to your application.")
    cleaned, counts = strip_contact_details(text)
    assert cleaned.splitlines() == [
        "Requirements", "- Python", "",
        "Questions? Contact [name removed] at [e-mail removed] or [phone removed].",
        "Recruiter: [name removed]",
        "Ihre Ansprechpartnerin: Frau [name removed], Tel. [phone removed]",
        "Heb je vragen? Neem contact op met [name removed].",
        "We look forward to your application."]
    assert counts == {"emails": 1, "phones": 2, "names": 4}
    for leftover in ("Jane", "Mustermann", "Anna", "Sanne", "@", "1234"):
        assert leftover not in cleaned


def test_ordinary_text_is_kept():
    text = ("Send your CV to jobs@example.org.\n"
            "Call 0044 20 7946 0958 between 9 and 17.\n"
            "Salary: 60.000 - 80.000 EUR per year, since 2019, 30 days of holiday.\n"
            "Contact the support team through the help centre.\n"
            "We can only reach out to shortlisted candidates.\n"
            "You will work with our Hiring Manager and Customer Support teams.\n"
            "Interview with the Engineering Lead (1 hour).\n"
            "- Recruiter Screening Call (30 min)\n"
            "For privacy questions contact Data Protection Officer.")
    cleaned, counts = strip_contact_details(text)
    assert cleaned.splitlines() == [
        "Send your CV to [e-mail removed].",
        "Call [phone removed] between 9 and 17.",
        "Salary: 60.000 - 80.000 EUR per year, since 2019, 30 days of holiday.",
        "Contact the support team through the help centre.",
        "We can only reach out to shortlisted candidates.",
        "You will work with our Hiring Manager and Customer Support teams.",
        "Interview with the Engineering Lead (1 hour).",
        "- Recruiter Screening Call (30 min)",
        "For privacy questions contact Data Protection Officer."]
    assert counts == {"emails": 1, "phones": 1, "names": 0}


def test_text_without_contact_details_is_unchanged():
    text = "About the role\n\nYou will build data pipelines.\n- SQL\n- Python"
    assert strip_contact_details(text) == (text, {"emails": 0, "phones": 0, "names": 0})


def test_nested_escaped_html_is_fully_converted():
    markup = "<p>&lt;p&gt;&lt;strong&gt;Your tasks&lt;/strong&gt;&lt;/p&gt;&lt;ul&gt;&lt;li&gt;SQL&lt;/li&gt;&lt;/ul&gt;</p>"
    assert html_to_text(markup) == "Your tasks\n\n- SQL"
