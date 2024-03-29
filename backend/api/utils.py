from rest_framework.pagination import PageNumberPagination


class PageLimitPaginator(PageNumberPagination):
    page_size = 5
    page_size_query_param = 'limit'
    max_page_size = 10


def delete_old_ingredients(recipe):
    old_ingredients = recipe.ingredients.all().delete()
    return old_ingredients
