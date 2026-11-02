from decimal import Decimal

from django import template

register = template.Library()


@register.filter
def money(value):
    try:
        return f"{Decimal(value):,.2f}"
    except (TypeError, ValueError, ArithmeticError):
        return "0.00"
