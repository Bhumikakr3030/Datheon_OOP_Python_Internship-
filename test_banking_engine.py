import unittest
from decimal import Decimal

from banking_engine import (
    Account, SavingsAccount, CheckingAccount, HighYieldAccount,
    TransactionProcessor
)


class BankingEngineTests(unittest.TestCase):
    def test_account_is_abstract(self):
        with self.assertRaises(TypeError):
            Account("A1", "Alice", "INR", "100")

    def test_deposit_and_ledger(self):
        account = SavingsAccount("S1", "Alice", "INR", "100")
        self.assertEqual(account.deposit("25.50"), Decimal("125.50"))
        self.assertEqual(account.transactions[-1].transaction_type, "DEPOSIT")
        self.assertEqual(account.transactions[-1].currency, "INR")

    def test_invalid_deposit_does_not_change_balance(self):
        account = SavingsAccount("S1", "Alice", "INR", "100")
        with self.assertRaises(ValueError):
            account.deposit("-1")
        self.assertEqual(account.balance, Decimal("100.00"))
        self.assertEqual(len(account.transactions), 0)

    def test_currency_is_attached_to_account(self):
        account = CheckingAccount("C1", "Bob", "USD", "10")
        self.assertEqual(account.currency, "USD")
        self.assertEqual(account.withdraw("2"), Decimal("8.00"))

    def test_insufficient_funds(self):
        account = SavingsAccount("S1", "Alice", "INR", "10")
        with self.assertRaises(ValueError):
            account.withdraw("11")
        self.assertEqual(account.balance, Decimal("10.00"))

    def test_checking_overdraft(self):
        account = CheckingAccount("C1", "Bob", "USD", "10",
                                  transaction_fee="1", overdraft_limit="5")
        self.assertEqual(account.withdraw("14"), Decimal("-4.00"))
        with self.assertRaises(ValueError):
            account.withdraw("2")

    def test_polymorphic_dispatch(self):
        processor = TransactionProcessor()
        savings = SavingsAccount("S1", "Alice", "INR", "12000",
                                 annual_rate="0.12", monthly_fee="0",
                                 minimum_balance="0")
        checking = CheckingAccount("C1", "Bob", "USD", "100",
                                   transaction_fee="2")
        processor.register(savings)
        processor.register(checking)
        interest = processor.process("S1", "interest")
        fee = processor.process("C1", "fees")
        self.assertEqual(interest, Decimal("120.00"))
        self.assertEqual(fee, Decimal("2.00"))

    def test_duplicate_account_rejected(self):
        processor = TransactionProcessor()
        processor.register(SavingsAccount("S1", "Alice"))
        with self.assertRaises(ValueError):
            processor.register(CheckingAccount("S1", "Bob"))

    def test_unsupported_currency_rejected(self):
        with self.assertRaises(ValueError):
            SavingsAccount("S1", "Alice", "XYZ", "10")

    def test_float_money_rejected(self):
        account = SavingsAccount("S1", "Alice")
        with self.assertRaises(ValueError):
            account.deposit(1.25)


if __name__ == "__main__":
    unittest.main()
