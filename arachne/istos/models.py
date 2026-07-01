from django.utils import timezone
from django.db import models
from pathlib import Path

form_type = [
    ("vid", "Vid"),
    ("pic", "Pic")
]

class LinkType(models.Model):
    slug = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=50, unique=True)

    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name

class ScrapeJob(models.Model):
    SCRAPE_TYPE = [
        ('scrape', 'Scrape'),
        ('update', 'Update'),
        ('extraction', 'Extraction')
    ]

    STATUS_CHOICES = [
        ('queued', 'Queued'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('paused', 'Paused'),
        ('failed', 'Failed'),
    ]

    url = models.URLField(max_length=200)
    scrape_type = models.CharField(choices=SCRAPE_TYPE)
    status = models.CharField(choices=STATUS_CHOICES, default='queued')
    created_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)
    linkType = models.ManyToManyField(LinkType, related_name='scrape_link_type')
    currIndex = models.IntegerField(null=True)

class Link(models.Model):
    url = models.URLField(max_length=200)
    site = models.CharField(max_length=100)
    title = models.CharField(max_length=100)
    dateGrabbed = models.DateField(default=timezone.now)
    lastUpdate = models.DateTimeField(null=True, default=None)
    lastExtract = models.DateTimeField(null=True, default=None)
    #Calls back to another link if scraped from that link
    hasParent = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name='children')
    linkType = models.ManyToManyField(LinkType, related_name='link_type')
    pages = models.JSONField(default=list)


class Items(models.Model):
    link = models.ForeignKey(Link, on_delete=models.CASCADE)#is link_id in DB
    url = models.URLField(max_length=100, null=True)
    site = models.CharField(max_length=100, null=True)
    type = models.CharField(max_length=50, null=True)
    dateGrabbed = models.DateField(default=timezone.now)
    saved = models.BooleanField(default=False)
    dateSaved = models.DateField(null=True)
    downloadBtn = models.BooleanField(default=False)

class Formats(models.Model):
    type = models.CharField(max_length=3, choices=form_type)
    formName = models.CharField(max_length=4)
    formSave = models.BooleanField(default=True)

class Settings(models.Model):
    settingName = models.CharField(max_length=100)
    on = models.BooleanField(default=False)
    addInfo = models.CharField(max_length=1000, null=True)
    tip = models.CharField(max_length=1000, null=True)

class Rules(models.Model):
    RULE_TYPES = [
        ("media", "MEDIA"),
        ("links", "LINKS")
    ]

    ACTION_CHOICES =  [
        ("include", "INCLUDE"),
        ("exclude", "EXCLUDE"),
    ]

    SELECTOR_TYPES =  [
        ("tag", "TAG"),
        ("id", "ID"),
        ("class", "CLASS"),
        ("name", "NAME")
    ]

    MATCH_TYPES =  [
        ("begins with", "BEGINS WITH"),
        ("ends with", "ENDS WITH"),
        ("contains", "CONTAINS"),
        ("is", "IS")
    ]

    on = models.BooleanField(default=True)
    rule_type = models.CharField(choices=RULE_TYPES)
    action_choice = models.CharField(choices=ACTION_CHOICES)
    selector_type = models.CharField(choices=SELECTOR_TYPES)
    match_type = models.CharField(choices=MATCH_TYPES)
    text = models.CharField(max_length=100)

