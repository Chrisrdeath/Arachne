from django.utils import timezone
from django.db import models
from pathlib import Path

form_type = [
    ("vid", "vid"),
    ("pic", "pic")
]

class Link(models.Model):
    url = models.URLField(max_length=200)
    site = models.CharField(max_length=100)
    title = models.CharField(max_length=100)
    dateGrabbed = models.DateField(default=timezone.now)
    lastUpdate = models.DateTimeField(default=timezone.now)
    #Calls back to another link if scraped from that link
    hasParent = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name='children')

class Items(models.Model):
    #is link_id in DB
    link = models.ForeignKey(Link, on_delete=models.CASCADE)
    url = models.URLField(max_length=100, null=True)
    site = models.CharField(max_length=100, null=True)
    type = models.CharField(max_length=50, null=True)
    dateGrabbed = models.DateField(default=timezone.now)
    saved = models.BooleanField(default=False)
    dateSaved = models.DateField(null=True)

class Formats(models.Model):
    type = models.CharField(max_length=3, choices=form_type)
    formName = models.CharField(max_length=4)
    formSave = models.BooleanField(default=True)

class Settings(models.Model):
    settingName = models.CharField(max_length=100)
    on = models.BooleanField(default=False)
    addInfo = models.CharField(max_length=1000, null=True)

class Rules(models.Model):
    types = [
        ("vid", "vid"),
        ("pic", "pic"),
        ("abs", "abs"),
        ("rel", "rel")
    ]

    CHOICE1 =  [
        ("LF", "Look for"),
        ("I", "Ignore")
    ]

    CHOICE2 =  [
        ("T", "Tag"),
        ("ID", "Id"),
        ("C", "Class"),
        ("N", "Name")
    ]

    CHOICE3 =  [
        ("BW", "Begins with"),
        ("EW", "Ends with"),
        ("C", "Contains"),
        ("IS", "Is")
        
    ]

    on = models.BooleanField(default=True)
    type = models.CharField(choices=types)
    choice1 = models.CharField(choices=CHOICE1)
    choice2 = models.CharField(choices=CHOICE2)
    choice3 = models.CharField(choices=CHOICE3)
    text = models.CharField(max_length=100)

    CHOICE1_DICT = dict(CHOICE1)
    CHOICE2_DICT = dict(CHOICE2)
    CHOICE3_DICT = dict(CHOICE3)

    def get_choice1_label(self):
        return self.CHOICE1_DICT.get(self.choice1, self.choice1)
    
    def get_choice2_label(self):
        return self.CHOICE2_DICT.get(self.choice2, self.choice2)
    
    def get_choice3_label(self):
        return self.CHOICE3_DICT.get(self.choice3, self.choice3)

