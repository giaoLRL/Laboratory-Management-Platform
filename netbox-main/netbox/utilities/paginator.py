from django.core.paginator import Page, Paginator

from netbox.config import get_config

__all__ = (
    'EnhancedPage',
    'EnhancedPaginator',
    'get_paginate_count',
)


class EnhancedPaginator(Paginator):
    # 10 放在首位：本平台默认每页 10 条（PAGINATE_COUNT = 10），
    # 下拉框必须包含当前页大小，否则用户选了其它值就回不到默认值。
    default_page_lengths = (
        10, 25, 50, 100, 250, 500, 1000
    )

    def __init__(self, object_list, per_page, orphans=None, **kwargs):

        # Determine the page size
        try:
            per_page = int(per_page)
            if per_page < 1:
                per_page = get_config().PAGINATE_COUNT
        except ValueError:
            per_page = get_config().PAGINATE_COUNT

        # 本平台要求"每页 N 条"严格等于 N：不再沿用 NetBox 默认的 orphans 合并策略
        # （per_page<=50 时 orphans=5，会把末页零头并进上一页——例如 12 条会在第 1 页
        # 显示 12 条，看起来像"每页 10 条"没生效）。调用方仍可显式传入 orphans 覆盖。
        if orphans is None:
            orphans = 0

        super().__init__(object_list, per_page, orphans=orphans, **kwargs)

    def _get_page(self, *args, **kwargs):
        return EnhancedPage(*args, **kwargs)

    def get_page_lengths(self):
        if self.per_page not in self.default_page_lengths:
            return sorted([*self.default_page_lengths, self.per_page])
        return self.default_page_lengths


class EnhancedPage(Page):

    def smart_pages(self):

        # When dealing with five or fewer pages, simply return the whole list.
        if self.paginator.num_pages <= 5:
            return self.paginator.page_range

        # Show first page, last page, next/previous two pages, and current page
        n = self.number
        pages_wanted = [1, n - 2, n - 1, n, n + 1, n + 2, self.paginator.num_pages]
        page_list = sorted(set(self.paginator.page_range).intersection(pages_wanted))

        # Insert skip markers
        skip_pages = [x[1] for x in zip(page_list[:-1], page_list[1:]) if (x[1] - x[0] != 1)]
        for i in skip_pages:
            page_list.insert(page_list.index(i), False)

        return page_list


def get_paginate_count(request):
    """
    Determine the desired length of a page, using the following in order:

        1. per_page URL query parameter
        2. Saved user preference
        3. PAGINATE_COUNT global setting.

    Return the lesser of the calculated value and MAX_PAGE_SIZE.
    """
    config = get_config()

    def _max_allowed(page_size):
        if config.MAX_PAGE_SIZE:
            return min(page_size, config.MAX_PAGE_SIZE)
        return page_size

    if 'per_page' in request.GET:
        try:
            per_page = int(request.GET.get('per_page'))
            return _max_allowed(per_page)
        except ValueError:
            pass

    if request.user.is_authenticated:
        per_page = request.user.config.get('pagination.per_page') or config.PAGINATE_COUNT
        return _max_allowed(per_page)

    return _max_allowed(config.PAGINATE_COUNT)
