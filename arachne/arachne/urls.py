from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static

from istos import views as istos

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', istos.index, name='index'),
    path('scraped-links/<str:type>/', istos.scraped_links, name='scraped_links'),
    path('scrape/<str:type>/', istos.scrape, name='scrape'),
    path('sec_scrape/<int:id>/<int:item_id>/', istos.sec_scrape, name='sec_scrape'),
    path('update/<int:id>/', istos.update, name='update'),
    path('delete/<int:id>/<str:delete_type>/', istos.delete, name='delete'),
    path('clear/', istos.clear, name='clear'),
    path('<int:id>/', istos.items, name='items'),
    path('back/<int:id>/', istos.get_page_num, name='back'),
    path('settings/', istos.settings, name='settings'),
    path('loading/<str:type>/', istos.loading, name='loading'),
    path('memory/<str:mem>/', istos.memory, name='memory'),
    path('rules/', istos.rules, name='rules'),

    #path('bookmarks/', istos.bookmark_extractor, name='bookmark_extractor'),

    path('error/', istos.error, name='error'),

]+ static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)