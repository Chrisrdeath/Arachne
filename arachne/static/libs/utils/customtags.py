from django import template

register = template.Library()

@register.filter
def get_value(dicionary, key):
    return dicionary.get(key)