from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from django.db import transaction

from apps.ledgers.services.helpers import build_two_line_entry, create_and_post_journal, get_configured_account
from apps.ledgers.services.types import JournalLineInput


@transaction.atomic
def post_savings_deposit(*, deposit_id: str, posting_date: date, amount: Decimal, cash_account_id: UUID, member_id: str, branch: UUID | None, created_by_id: UUID | None, currency: str = "UGX"):
    savings = get_configured_account("member_savings", branch)
    return create_and_post_journal(
        reference=f"SAV-{deposit_id}",
        journal_type="member_savings_deposit",
        posting_date=posting_date,
        description=f"Member savings deposit {deposit_id}",
        source_module="sacco",
        source_id=deposit_id,
        branch=branch,
        created_by_id=created_by_id,
        idempotency_key=f"savings-deposit:{deposit_id}",
        lines=build_two_line_entry(
            debit_account_id=cash_account_id,
            credit_account_id=savings.id,
            amount=amount,
            currency=currency,
            description=f"Savings deposit {deposit_id}",
            branch=branch,
            party_type="member",
            party_id=member_id,
        ),
    )


@transaction.atomic
def post_loan_disbursement(*, disbursement_id: str, posting_date: date, amount: Decimal, cash_account_id: UUID, member_id: str, branch: UUID | None, created_by_id: UUID | None, currency: str = "UGX"):
    loan_receivable = get_configured_account("loan_receivables", branch)
    return create_and_post_journal(
        reference=f"LOAN-{disbursement_id}",
        journal_type="loan_disbursement",
        posting_date=posting_date,
        description=f"Loan disbursement {disbursement_id}",
        source_module="sacco",
        source_id=disbursement_id,
        branch=branch,
        created_by_id=created_by_id,
        idempotency_key=f"loan-disbursement:{disbursement_id}",
        lines=build_two_line_entry(
            debit_account_id=loan_receivable.id,
            credit_account_id=cash_account_id,
            amount=amount,
            currency=currency,
            description=f"Loan disbursement {disbursement_id}",
            branch=branch,
            party_type="member",
            party_id=member_id,
        ),
    )


@transaction.atomic
def post_loan_repayment(
    *,
    repayment_id: str,
    posting_date: date,
    principal_amount: Decimal,
    interest_amount: Decimal,
    cash_account_id: UUID,
    member_id: str,
    branch: UUID | None,
    created_by_id: UUID | None,
    currency: str = "UGX",
):
    loan_receivable = get_configured_account("loan_receivables", branch)
    interest_income = get_configured_account("interest_income", branch)
    total = principal_amount + interest_amount
    lines: list[JournalLineInput] = [
        JournalLineInput(
            account_id=cash_account_id,
            debit_foreign=total,
            debit_base=total,
            currency_code=currency,
            description=f"Loan repayment cash received {repayment_id}",
            branch=branch,
            party_type="member",
            party_id=member_id,
        ),
        JournalLineInput(
            account_id=loan_receivable.id,
            credit_foreign=principal_amount,
            credit_base=principal_amount,
            currency_code=currency,
            description=f"Principal repayment {repayment_id}",
            branch=branch,
            party_type="member",
            party_id=member_id,
        ),
    ]
    if interest_amount > Decimal("0.00"):
        lines.append(
            JournalLineInput(
                account_id=interest_income.id,
                credit_foreign=interest_amount,
                credit_base=interest_amount,
                currency_code=currency,
                description=f"Interest income on repayment {repayment_id}",
                branch=branch,
                party_type="member",
                party_id=member_id,
            )
        )
    return create_and_post_journal(
        reference=f"REPAY-{repayment_id}",
        journal_type="loan_repayment",
        posting_date=posting_date,
        description=f"Loan repayment {repayment_id}",
        source_module="sacco",
        source_id=repayment_id,
        branch=branch,
        created_by_id=created_by_id,
        idempotency_key=f"loan-repayment:{repayment_id}",
        lines=lines,
        transaction_currency_code=currency,
    )


@transaction.atomic
def post_interest_accrual(*, accrual_id: str, posting_date: date, amount: Decimal, member_id: str, branch: UUID | None, created_by_id: UUID | None, currency: str = "UGX"):
    receivable = get_configured_account("interest_receivable", branch)
    income = get_configured_account("interest_income", branch)
    return create_and_post_journal(
        reference=f"IACC-{accrual_id}",
        journal_type="interest_accrual",
        posting_date=posting_date,
        description=f"Interest accrual {accrual_id}",
        source_module="sacco",
        source_id=accrual_id,
        branch=branch,
        created_by_id=created_by_id,
        idempotency_key=f"interest-accrual:{accrual_id}",
        lines=build_two_line_entry(
            debit_account_id=receivable.id,
            credit_account_id=income.id,
            amount=amount,
            currency=currency,
            description=f"Interest accrual {accrual_id}",
            branch=branch,
            party_type="member",
            party_id=member_id,
        ),
    )


@transaction.atomic
def post_penalty_charge(*, charge_id: str, posting_date: date, amount: Decimal, member_id: str, branch: UUID | None, created_by_id: UUID | None, currency: str = "UGX"):
    receivable = get_configured_account("interest_receivable", branch)
    income = get_configured_account("penalty_income", branch)
    return create_and_post_journal(
        reference=f"PEN-{charge_id}",
        journal_type="penalty_charge",
        posting_date=posting_date,
        description=f"Penalty charge {charge_id}",
        source_module="sacco",
        source_id=charge_id,
        branch=branch,
        created_by_id=created_by_id,
        idempotency_key=f"penalty-charge:{charge_id}",
        lines=build_two_line_entry(
            debit_account_id=receivable.id,
            credit_account_id=income.id,
            amount=amount,
            currency=currency,
            description=f"Penalty charge {charge_id}",
            branch=branch,
            party_type="member",
            party_id=member_id,
        ),
    )
