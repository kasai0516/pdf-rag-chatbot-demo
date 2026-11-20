"""Generate the fictional sample documents in ./samples (all content is made up)."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from minipdf import write_pdf  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "samples")

TERMS = [
    [
        "Northwind Cloud - Terms of Service (fictional sample)",
        "",
        "1. Plans and billing",
        "Northwind Cloud offers a monthly plan and an annual plan.",
        "Monthly plans are billed on the same day each month.",
        "Annual plans are billed once per year and include two free months.",
        "Prices are shown without tax. Tax is added at checkout where required.",
        "",
        "2. Refunds",
        "Annual plans can be refunded in full within 14 days of purchase.",
        "Monthly plans are not refundable, but you can cancel at any time.",
        "After cancellation, the service stays active until the end of the paid period.",
    ],
    [
        "3. Data and backups",
        "Customer data is stored in the EU region by default.",
        "Backups are taken every 24 hours and kept for 30 days.",
        "You can export all of your data as JSON from the settings page.",
        "When an account is closed, data is deleted within 60 days.",
        "",
        "4. Service availability",
        "Northwind Cloud targets 99.9 percent monthly uptime for paid plans.",
        "Planned maintenance is announced at least 72 hours in advance.",
        "If uptime falls below the target, customers receive a 10 percent service credit.",
    ],
    [
        "5. Support",
        "Support is available by email on all plans.",
        "Business plans also include live chat from 9:00 to 18:00 CET on weekdays.",
        "The first response time is within one business day for email.",
        "Critical incidents on Business plans receive a response within 2 hours.",
        "",
        "6. Account security",
        "Two-factor authentication can be enabled for every user.",
        "Administrators can require two-factor authentication for the whole team.",
        "Password resets are sent only to the verified email address.",
    ],
]

PRICING = [
    [
        "Northwind Cloud - Price List (fictional sample)",
        "",
        "Starter plan: 12 USD per user per month, up to 5 users.",
        "Team plan: 25 USD per user per month, up to 50 users.",
        "Business plan: 40 USD per user per month, unlimited users.",
        "Annual billing gives two free months on every plan.",
        "Extra storage costs 5 USD per 100 GB per month.",
    ]
]


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    write_pdf(os.path.join(OUT, "northwind_terms.pdf"), TERMS)
    write_pdf(os.path.join(OUT, "northwind_pricing.pdf"), PRICING)
    print("wrote 2 sample PDFs")


if __name__ == "__main__":
    main()
