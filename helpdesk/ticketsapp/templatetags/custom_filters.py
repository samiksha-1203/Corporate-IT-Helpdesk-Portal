from django import template

register = template.Library()

@register.filter
def abs_val(value):
    try:
        return abs(value)
    except:
        return value
