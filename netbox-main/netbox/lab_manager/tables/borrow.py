import django_tables2 as tables

from netbox.tables import NetBoxTable
from netbox.tables.columns import ChoiceFieldColumn

from ..models import HardwareBorrowRecord


class HardwareBorrowRecordTable(NetBoxTable):
    hardware = tables.Column(linkify=True)
    borrower = tables.Column(linkify=True)
    status = ChoiceFieldColumn()
    borrow_date = tables.DateTimeColumn()
    expected_return_date = tables.DateTimeColumn()
    actual_return_date = tables.DateTimeColumn()

    class Meta(NetBoxTable.Meta):
        model = HardwareBorrowRecord
        fields = (
            'pk', 'id', 'hardware', 'borrower', 'status',
            'borrow_date', 'expected_return_date', 'actual_return_date',
            'purpose', 'tags', 'created', 'last_updated',
        )
        default_columns = (
            'hardware', 'borrower', 'status', 'borrow_date',
            'expected_return_date', 'purpose',
        )
