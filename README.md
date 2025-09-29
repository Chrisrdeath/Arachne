# Arachne - Django Webscraper
A Webscraper that allows you to scrape webpages for pictures and videos as well as relative links and absolute links to allow for a spider web of link scraping

## Prerequisites
Gecko Driver - https://github.com/mozilla/geckodriver/releases

## Setup
1.Create Virtual Environment:
```bash
    py -m venv <venv_name>
```
2.Start Virtual Environment:<br>
Windows:
```cmd
    <venv_name>\Scripts\activate
```
macOS/Linux:
```bash
    source <venv_name>/bin/activate
```
3.Install Requirements
```bash
    pip install -r requirements.txt
```

## Running the server
1.Go to `arachne`
```bash
    cd arachne
```
2.Apply migrations
```bash
    py manage.py migrate
```
3.Start Django development server
```bash
    py manage.py runserver
```
4.Start background tasks:
```bash
    py manage.py process_tasks
```
Or for multiple processors
```bash
    py dev_workers.py <int:Num background workers>
```
*Using to many may cause a 429 error from to many requests*

## Editing
Sass - https://sass-lang.com/install/

```bash
    sass --watch --no-source-map <file.scss> <file.css>
```