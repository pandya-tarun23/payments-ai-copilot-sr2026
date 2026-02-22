# MT103 Key Fields

20 - Sender Reference
32A - Value Date, Currency, Amount
50K - Ordering Customer
59 - Beneficiary Customer
71A - Charges (OUR/SHA/BEN)
121 - UETR

# pacs.008 Key Elements

GrpHdr/MsgId - Message Identification
IntrBkSttlmAmt - Interbank Settlement Amount
Dbtr/Nm - Debtor Name
Cdtr/Nm - Creditor Name
ChrgBr - Charge Bearer
UETR - Unique End-to-End Transaction Reference

# pacs.002 Common Reject Codes

AC04 - Closed account
AM04 - Insufficient funds
AG01 - Transaction forbidden

# UETR Usage

UETR is present in:
- MT103 field 121
- pacs.008 element UETR
- Used for end-to-end tracking across correspondent banks