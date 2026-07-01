import json

from django.core.paginator import Paginator
from django.db.models import Count
from django.shortcuts import redirect
from django.shortcuts import render
from urllib.parse import unquote
from datetime import datetime, timedelta

from .models import *
from .utils import *
from background_task.models import Task

from static.libs.extracting import bookmark_extractor as bkmk
from static.libs.utils import exceptions as exc

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


paginator_objects = 12

#Dashboard
def index(request, filter=None):
    time_ranges = {
        '1d': timedelta(days=1),
        '1w': timedelta(weeks=1),
        '1m': timedelta(days=30),
    }

    range_time_key = request.GET.get('range', '1d')
    status_filter = request.GET.get('status', '')
    type_filter = request.GET.get('type', '')

    since = datetime.now() - time_ranges.get(range_time_key, time_ranges['1d'])


    recent_jobs = ScrapeJob.objects.filter(created_at__gte=since)

    if status_filter:
        recent_jobs = recent_jobs.filter(status=status_filter)

    if type_filter:
        recent_jobs = recent_jobs.filter(scrape_type=type_filter)

    running_jobs = ScrapeJob.objects.filter(status = 'running').count()
    queued_jobs = ScrapeJob.objects.filter(status = 'queued').count()
    completed_jobs = ScrapeJob.objects.filter(status = 'completed').count()
    failed_jobs = ScrapeJob.objects.filter(status = 'failed').count()

    dash_data = {
        'running' : running_jobs,
        'queued': queued_jobs,
        'completed': completed_jobs,
        'failed': failed_jobs,
        'recent_jobs': recent_jobs,
        'current_range': range_time_key,
        'type': status_filter,
        'status': type_filter,
    }

    return render(request, 'index.html', {'data': dash_data})

#Enter URL here
def scrape(request, type):
    match type:
        case "links":
            h1 = "Links"
        case "media":
            h1 = "Media"
        case "video":
            h1 = "Video"
        case _:
            return redirect('/')

    request.session['type'] = type   

    if request.method == "POST":
        url = request.POST.get('url', '')

        try:
            Validate.URL(url)
        except exc.URLError as e:
            return error(request, e)

        if(Link.objects.filter(url=url).exists()):
            curr_link = Link.objects.get(url=url)
            curr_job = ScrapeJob.objects.create(url=url, scrape_type='update')

            link_types = LinkType.objects.filter(slug=type)
            curr_job.linkType.add(*link_types)

            request.session['task_id'] = curr_job.id

            link_type_names = list(link_types.values_list('slug', flat=True))

            scrape_items(curr_link.url, link_type_names, curr_job.id, priority=0)            
            return redirect('/loading/update/')

        else:
            curr_job = ScrapeJob.objects.create(url=url, scrape_type='scrape')

            link_types = LinkType.objects.filter(slug=type)
            curr_job.linkType.add(*link_types)

            request.session['task_id'] = curr_job.id

            link_type_names = list(link_types.values_list('slug', flat=True))

            scrape_items(url, link_type_names, curr_job.id, priority=0)
            return redirect('/loading/first/')    
    
    scrape_data = {
        'h1' : h1
    }
    return render(request, 'scrape.html', {'data': scrape_data})

#View Scraped links
def scraped_links(request, type):
    request.session['media_type'] = type
    LINK_TYPE = ['scraped', 'media', 'links', 'video']

    if type not in LINK_TYPE:
        return redirect('/')

    selected_site = request.GET.get('site_filter')
        
    site_options = Link.objects.values_list('site', flat=True).distinct()

    if type == 'scraped':
        data = Link.objects.all()

    else:
        linkType = LinkType.objects.get(slug=type)
        linkTypeID = linkType.id
        linkTypeName = linkType.slug

        if selected_site:
            data = Link.objects.filter(linkType=linkTypeID, site=selected_site).annotate(item_count=Count('items')).order_by('id')
        else:
            data = Link.objects.filter(linkType=linkTypeID).annotate(item_count=Count('items')).order_by('id')

    page_number = request.GET.get('page', 1)
    paginator = Paginator(data, paginator_objects)

    page_obj = {
        'link_type': linkTypeName,
        'page_obj' : paginator.get_page(page_number),
        'site_options': site_options,
        'selected_site': selected_site
    }
    
    return render(request, 'scraped-links.html', {'data': page_obj})

#Scraping link from another link
def sec_scrape(request, id, item_id):
    link = Items.objects.get(id=item_id)

    link.saved = 1
    link.dateSaved =  timezone.now()
    link.save()

    curr_job = ScrapeJob.objects.create(url=url, scrape_type='scrape', created_at=timezone.now())

    request.session['task_id'] = curr_job.id
    request.session['parent_id'] = id

    scrape_items(link.url, 'second', curr_job.id)
    
    return redirect('/loading/second/')

#Update scraped data
def update(request, id):
    update_link = Link.objects.get(id=id)

    update_link.lastUpdate = timezone.now()
    update_link.save()

    curr_job = ScrapeJob.objects.create(url=update_link.url, scrape_type='update')

    link_types = update_link.linkType.all()
    for lt in link_types:
        curr_job.linkType.add(lt)

    request.session['task_id'] = curr_job.id

    link_type_names = list(link_types.values_list('slug', flat=True))

    scrape_items(update_link.url, link_type_names, curr_job.id, priority=0)            
    return redirect('/loading/update/')

#Delete one item/link from DB
def delete(request, id, delete_type):
    previous_url = request.META.get('HTTP_REFERER')
    
    match(delete_type):
        case "Link":
            Link.objects.filter(id=id).first().delete()
        case "Item":
            Items.objects.filter(id=id).first().delete()

    media_type = request.session.get('media_type')

    return redirect(f'/scraped-links/{media_type}/')

#Deletes all Links
def clear(request):
    Link.objects.all().delete()

    media_type = request.session.get('media_type')

    return redirect(f'/scraped-links/{media_type}/')

#Item page
def items(request, id):
    #For saving items to computer
    if request.method == "POST":
        ids = request.POST.get('save_form_input', '')
        parent_id = id
        
        split_ids = ids.split(',')
        choice = split_ids[0]
        del split_ids[0]
        ids = ','.join(split_ids)
            
        match choice:
            case "save":
                link = Link.objects.get(id=parent_id)
                url = link.url

                link.lastExtract = timezone.now()
                link.save()
                
                curr_job = ScrapeJob.objects.create(url=url, scrape_type='extraction')

                extract_items(parent_id, ids, curr_job.id, priority=1)
                        
                return get_page_num(request, parent_id)
                
            case "delete":
                delete_items(parent_id, ids)

    link = Link.objects.get(id=id)

    auto_update = Settings.objects.get(settingName = "auto_update")

    if(auto_update.on):
        last_update = link.lastUpdate
        time_diff = (timezone.now() - last_update)
        minutes = time_diff.total_seconds() / 60
        print(f"{minutes:.2f} minutes")

        if(minutes>int(auto_update.addInfo)):    
            scrape_items(link.url)

            link.lastUpdate = timezone.now()
            link.save()

            task = Task.objects.filter(task_name='istos.utils.scrape_items').last()

            request.session['task_id'] = task.id
            request.session['curr_id'] = link.id

            return redirect('/loading/auto_update/')

    items = Items.objects.filter(link_id=id).order_by('id')

    item_info = {
        "pics": 0,
        "vids": 0,
        "abs": 0,
        "rels": 0
    }

    for item in items:
        match item.type:
            case "pic":
                item_info["pics"] += 1

            case "vid":
                item_info["vids"] += 1

            case "abs":
                item_info["abs"] += 1

            case "rel":
                item_info["rels"] += 1
            
    

    link_info = (link.url, link.title, link.id)

    data = {
        "items" : items,
        "item_info": item_info,
        "link_info": link_info,
    }

    if link.hasParent:
        parent = link.hasParent
        parent_info = (parent.url, parent.title, parent.id)
        data["parent_info"] = parent_info
    
    return render(request, 'items.html', {'data': data})

#Settings page
def settings(request):
    if request.method == "POST":
        picformats = Formats.objects.filter(type='pic').values_list("formName", "formSave")
        vidformats = Formats.objects.filter(type='vid').values_list("formName", "formSave")
        settings = Settings.objects.exclude(id__in=[1, 6, 7]).values_list('settingName', 'on') 
        rules = Rules.objects.values_list('id', 'on')

        for pic in picformats:
            value = request.POST.get(pic[0], 'off')
            previous = pic[1]

            current = (value != 'off')

            if current != previous:
                update_db = Formats.objects.get(formName=pic[0])
                update_db.formSave = current
                update_db.save()

        for vid in vidformats:
            value = request.POST.get(vid[0], 'off')
            previous = vid[1]

            current = (value != 'off')

            if current != previous:
                update_db = Formats.objects.get(formName=vid[0])
                update_db.formSave = current
                update_db.save()

        for sett in settings:
            value = request.POST.get(sett[0], 'off')
            previous = sett[1]

            current = (value != 'off')

            if current != previous:
                update_db = Settings.objects.get(settingName=sett[0])
                update_db.on = current
                update_db.save()

        for rule in rules:
            rule_id = str(rule[0])
            on = request.POST.get(rule_id, 'off')

            previous = rule[1]
            current = (on != 'off')

            if current != previous:
                update_db = Rules.objects.get(id=rule[0])
                update_db.on = current
                update_db.save()
        
    saveloc = Settings.objects.filter(settingName='save_loc').values_list("addInfo", flat=True).first()

    settings_labels = ["Go To Items", "Absolute Links", "Related Links", "Relative Links"]
    settings_info = ["Automatically go to items after scraping", "Grab absolute links", "Absolute links will be related to parent", "Grab relative links"]

    settings = Settings.objects.exclude(id=1).values_list('settingName', 'on')
    picformats = Formats.objects.filter(type='pic').values_list("formName", "formSave")
    vidformats = Formats.objects.filter(type='vid').values_list("formName", "formSave")

    rules = Rules.objects.all()

    full_settings = [
        {
            'name': setting[0],
            'on': setting[1],
            'label': label,
            'info': info
        }
        for setting, label, info in zip(settings, settings_labels, settings_info)
    ]

    data = {
        "savelocation": saveloc,
        "settings": full_settings,
        "picformats": picformats,
        "vidformats": vidformats,
        "rules": rules
    }

    return render(request, 'settings.html', {'data': data})

#Loading page while Scraping is happening -- Polling
def loading(request, type):
    parent_id = 0
    current_id = 0

    match type:
        case "first":
            h1 = "Scraping Website"
        case "second":
            h1 = "Scraping Website"
        case "update":
            h1 = "Updating Items"
        case "auto_update":
            h1 = "Updating Items"

    #Task Info
    task_id = request.session.get('task_id')
    curr_task = ScrapeJob.objects.get(id=task_id)

    #Setting
    go_to_items = Settings.objects.get(settingName = 'auto_items')

    if curr_task.status == "running" or curr_task.status == "queued" :
        #Get url and put in header
        return render(request, 'loading.html', {'data': h1})

    ScrapeJob.objects.filter(id=curr_task.id).update(completed_at=timezone.now())
    link = Link.objects.get(url=curr_task.url)
    current_id = link.id

    if(type=="second"):
        parent_link(link.id, parent_id)
    elif(type=="auto_update"):
        return redirect(f'/{current_id}')

    if go_to_items.on:
        if current_id == 0:
            return redirect(f'/{link.id}')
        else:
            return redirect(f'/{current_id}')
    else:
        return get_page_num(request, current_id)

#For paginator to return to correct page
def get_page_num(request, id):
    try:
        if id:
            link = Link.objects.get(id=id)
        else:
            #Task Info
            task_id = request.session.get('task_id')
            curr_task = ScrapeJob.objects.get(id=task_id)
            link = Link.objects.get(url=curr_task.url)

        #Returns to Index if page not found
        if not link:
            print("LinkID not found")
            return redirect('/')

        link_types = link.linkType.all()
        type_count = link_types.count()

        if(type_count > 1):
            #More than one link types, sort all
            #id__lt - id less than
            position = Link.objects.filter(id__lt=link.id).count()
            url_lt = 'scraped'
        else:
            #One scrape type, sort link type
            #Filter order matters
            position = Link.objects.filter(linkType = link_types[0], id__lt=link.id).count()
            url_lt = link_types[0].slug
        
        page_number = (position // paginator_objects) + 1

        return redirect(f'/scraped-links/{url_lt}/?page={page_number}')
        
    except Exception as e:
        return redirect(f'/scraped-links/{url_lt}/')

#Scraping rules
def rules(request):
    if request.method == "POST":
        type = request.POST.get('type')
        choice1 = request.POST.get('choice1')
        choice2 = request.POST.get('choice2')
        choice3 = request.POST.get('choice3')
        text = request.POST.get('addInfo')

        rule = Rules.objects.filter(
            type=type, 
            choice1=choice1, 
            choice2=choice2, 
            choice3=choice3, 
            text=text
            ).exists()

        if not rule:
            Rules.objects.create(
                type=type, 
                choice1=choice1, 
                choice2=choice2, 
                choice3=choice3, 
                text=text
            )
        
    return redirect('/settings/')

#Error Page
def error(request, e):
    return render(request, 'error.html', {'data': e})


    

    

