import re
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum

import httpx2
import pandas as pd
import streamlit as st
from httpx2 import QueryParams
from pydantic import BaseModel, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

st.set_page_config(layout="wide")


class Settings(BaseSettings):
    token: SecretStr
    cookie: SecretStr
    model_config = SettingsConfigDict(env_file=".env", env_prefix="FIREFLY_")


settings = Settings.model_validate({})


class ShortAccountTypeProperty(StrEnum):
    ASSET = "asset"
    EXPENSE = "expense"
    IMPORT = "import"
    REVENUE = "revenue"
    CASH = "cash"
    LIABILITY = "liability"
    LIABILITIES = "liabilities"
    INITIAL_BALANCE = "initial-balance"
    RECONCILIATION = "reconciliation"


class AccountsArray(BaseModel):
    class AccountRead(BaseModel):
        class AccountProperties(BaseModel):
            name: str
            type: ShortAccountTypeProperty

        id: int
        attributes: AccountProperties

    data: list[AccountRead]


@st.cache_data
def get_all_accounts(
    account_type: ShortAccountTypeProperty | None = None,
) -> AccountsArray:
    headers = {"authorization": f"Bearer {settings.token.get_secret_value()}"}
    url = "http://localhost/api/v1/accounts"
    params = None
    if account_type is not None:
        params = QueryParams({"type": account_type})
    response = httpx2.get(url, headers=headers, params=params)
    response.raise_for_status()
    return AccountsArray.model_validate_json(response.content)


class NetWorthData(BaseModel):
    class Dataset(BaseModel):
        currency_symbol: str
        data: list[Decimal]
        label: str

    datasets: list[Dataset]
    labels: list[date]

    @field_validator("labels", mode="before")
    @classmethod
    def parse_labels(cls, value: list[str]) -> list[date]:
        # January 1st, 2026; January 8th, 2026; etc
        labels: list[date] = []
        for label in value:
            cleaned = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", label)
            labels.append(datetime.strptime(cleaned, "%B %d, %Y").date())
        return labels


@st.cache_data
def get_net_worth_data(
    accounts: list[int], start_date: date, end_date: date
) -> NetWorthData:
    headers = {"cookie": settings.cookie.get_secret_value()}
    api_url = (
        "http://localhost/chart/report/net-worth/{accounts}/{start_date}/{end_date}"
    )
    url = api_url.format(
        accounts=",".join(str(account_id) for account_id in accounts),
        start_date=start_date.strftime("%Y%m%d"),
        end_date=end_date.strftime("%Y%m%d"),
    )
    response = httpx2.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return NetWorthData.model_validate_json(response.content)


def build_chart_frame(data: NetWorthData) -> pd.DataFrame:
    df = pd.DataFrame({"Date": data.labels, "Total": data.datasets[0].data})
    df["Date"] = pd.to_datetime(df["Date"])
    df["Total"] = df["Total"].astype(float)
    return df


def main() -> None:
    st.title("Net worth chart")

    try:
        all_asset_accounts = get_all_accounts(ShortAccountTypeProperty.ASSET)
    except Exception as exc:
        st.error(f"Failed to load accounts: {exc}")
        st.stop()

    all_asset_ids = sorted(account.id for account in all_asset_accounts.data)

    selected_accounts = st.multiselect(
        "Asset accounts",
        options=all_asset_ids,
        default=all_asset_ids,
        format_func=lambda account_id: next(
            account.attributes.name
            for account in all_asset_accounts.data
            if account.id == account_id
        ),
    )

    default_start = date(2022, 3, 22)
    start_date = st.date_input("Start date", value=default_start)
    default_end = datetime.now().date()
    end_date = st.date_input("End date", value=default_end) + timedelta(days=7)

    if not selected_accounts:
        st.warning("Select at least one asset account to view the chart.")
        st.stop()

    if start_date > end_date:
        st.error("Start date must be on or before end date.")
        st.stop()

    try:
        net_worth_data = get_net_worth_data(selected_accounts, start_date, end_date)
    except Exception as exc:
        st.error(f"Failed to fetch net worth data: {exc}")
        st.stop()

    chart_totals = build_chart_frame(net_worth_data)

    st.subheader("Net worth")
    st.line_chart(chart_totals, x="Date", y="Total")

    with st.expander("Raw data"):
        st.write(chart_totals)


if __name__ == "__main__":
    main()
