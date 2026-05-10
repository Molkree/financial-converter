from datetime import date, datetime, timedelta
from decimal import Decimal

import httpx
import typer
from pydantic import BaseModel, Field
from pydantic_extra_types.currency_code import ISO4217

TARGET_CURRENCIES = {
    ISO4217("EUR"),
    ISO4217("GBP"),
    ISO4217("RUB"),
    ISO4217("TRY"),
    ISO4217("USD"),
}
BANK_URL = (
    "https://nbg.gov.ge/gw/api/ct/monetarypolicy/currencies/en/json/?date={target_date}"
)
FIREFLY_API_URL = "http://localhost/api/v1/exchange-rates"


class CurrencyRate(BaseModel):
    code: ISO4217
    quantity: int
    rate: Decimal
    valid_from_date: date = Field(alias="validFromDate")


def get_currency_rates(target_date: date) -> dict[ISO4217, CurrencyRate]:
    url = BANK_URL.format(target_date=target_date)
    response = httpx.get(url)
    response.raise_for_status()
    data = response.json()
    rates: dict[ISO4217, CurrencyRate] = {}
    for item in data[0]["currencies"]:
        if item["code"] not in TARGET_CURRENCIES:
            continue
        rate = CurrencyRate(**item)
        rates[rate.code] = rate
    return rates


def add_currency_rates(token: str, start_dt: datetime, end_dt: datetime) -> None:
    current_date = end_dt.date()
    while current_date >= start_dt.date():
        rates = get_currency_rates(current_date)
        print(f"Currency rates for {current_date}:")
        for code, rate in rates.items():
            normalized_rate = str(rate.rate / rate.quantity)
            print(f"{code}: {normalized_rate}")
            httpx.post(
                FIREFLY_API_URL,
                headers={"authorization": f"Bearer {token}"},
                json={
                    "from": code,
                    "to": "GEL",
                    "rate": normalized_rate,
                    "date": str(current_date),
                },
                timeout=60,
            )
        current_date -= timedelta(days=1)


if __name__ == "__main__":
    typer.run(add_currency_rates)
