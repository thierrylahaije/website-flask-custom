from flask import Flask, render_template, request, redirect, abort, session, jsonify, g
from flask_assets import Environment, Bundle
from datetime import datetime
from functions import build_data_dict, fetch_contributions_for_the_single_contributor, generate_table_of_contents, get_breadcrumbs, find_related_articles, calculate_reading_time, fetch_meta_data, recently_published
import os
from models import db, articles, Contributors, blogs, Topics, PageViews
from html_parser import htmlize
from redirectstsh import setup_redirects
from flask_session import Session
from datetime import datetime
from collections import defaultdict

# Initialize App
app = Flask(__name__, static_url_path='/static')

# DB
db_filename = 'tsh.db'
db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), db_filename))
db_uri = f'sqlite:///{db_path}'  

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Templates and assets
app.config['TEMPLATES_AUTO_RELOAD'] = False # Only true when Debugging
app.config['CACHE'] = True  # Only false when Debugging
app.config['ASSETS_DEBUG'] = False  # Only true for Debugging

# Security settings
app.config['SESSION_COOKIE_SECURE'] = True  # Only false when Debugging
app.config['REMEMBER_COOKIE_SECURE'] = True  # Only false when Debugging
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Only false when Debugging
app.config['REMEMBER_COOKIE_HTTPONLY'] = True  # Only false when Debugging

# Session Settings (admin)
app.config['SECRET_KEY'] = 'supersecretkey'
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

# Initialize SQLAlchemy with the app
db.init_app(app)

# Build & Register SCSS Bundle
assets = Environment(app)

scss_bundle = Bundle(
    'scss/bootstrap.scss',  
    output='css/main.css',
    filters='scss',
)

assets.register('scss_all', scss_bundle)

# Custom filter for dates
@app.template_filter('formatdate')
def formatdate(value, format="%Y-%m-%d"):
    if value is None:
        return ""
    date = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S%z")
    return date.strftime(format)

### ADMIN AREA ###
@app.route('/admin/dashboard')
def admin_dashboard():
    return render_template('admin/dashboard.html')

@app.route('/admin/write-article')
def admin_write_article():
    return render_template('admin/write-article.html')

@app.route('/admin/render', methods=['GET'])
def render_template_view():

    # Render content
    content = session.get('content', 'Dit is de standaard inhoud van render.html.')
    article_content = htmlize(content)
    table_of_contents = generate_table_of_contents(content)
    if (len(content) > 0):
            reading_time = calculate_reading_time(content)

    # Render variables
    title = session.get('title', 'Default Title')
    description = session.get('description', 'Default Description')
    author = session.get('author', 'Default Author')
    draft = session.get('draft', 'false')
    data_dict = build_data_dict(Topics, articles)
    return render_template('admin/render/render.html', 
                           content=article_content, 
                           title=title, 
                           description=description, 
                           author=author, 
                           draft=draft,
                           assets=assets,
                           table_of_contents=table_of_contents, reading_time=reading_time, data_dict=data_dict)

@app.route('/update_content', methods=['POST'])
def update_content():
    data = request.get_json()
    session['content'] = data.get('content', '')
    session['title'] = data.get('title', 'Default Title')
    session['description'] = data.get('description', 'Default Description')
    session['author'] = data.get('author', 'Default Author')
    session['draft'] = data.get('draft', 'false')
    return jsonify({'success': True})

### END ADMIN AREA
### STATS AREA
@app.route('/api/pageview', methods=['POST'])
def store_pageview():
  # Access data from the AJAX request
  page_url = request.json.get('page_url')

  if not request.path.startswith('/static'):
    session_length = request.json.get('session_length')  # Access session length from request

    # Convert start_time from string to datetime object
    start_time_obj = datetime.now()

    # Create a new PageViews object with the data
    page_view = PageViews(page=page_url, viewed_date=start_time_obj.date(), viewed_time=start_time_obj.time(), session_length=session_length)

    # Add the object to the database session
    db.session.add(page_view)

    # Commit the changes to the database
    db.session.commit()

    return "Pageview data stored successfully!", 201 
  
  else:
    return "Pageview path starts with static.", 403

@app.route('/admin/stats')
def stats():
    stats = PageViews.query.all()
    views_per_day = defaultdict(int)
    page_stats = defaultdict(lambda: {'count': 0, 'total_session_length': 0})
    time_per_page = defaultdict(lambda: defaultdict(int))
    session_length_per_day = defaultdict(lambda: {'total_length': 0, 'count': 0})

    for stat in stats:
        views_per_day[stat.viewed_date] += 1
        page_stats[stat.page]['count'] += 1
        page_stats[stat.page]['total_session_length'] += stat.session_length
        time_per_page[stat.viewed_date][stat.page] += stat.session_length
        session_length_per_day[stat.viewed_date]['total_length'] += stat.session_length
        session_length_per_day[stat.viewed_date]['count'] += 1

    # Prepare data for Morris.js
    morris_data = [{"y": date.strftime('%Y-%m-%d'), "a": views_per_day[date]} for date in sorted(views_per_day.keys())]

    # Calculate average session length per page
    page_stats_data = []
    for page, data in page_stats.items():
        avg_session_length = data['total_session_length'] / data['count'] if data['count'] > 0 else 0
        page_stats_data.append({'page': page, 'total_views': data['count'], 'avg_session_length': avg_session_length})

    # Prepare data for average session length per day chart
    session_length_data = []
    for date in sorted(session_length_per_day.keys()):
        total_length = session_length_per_day[date]['total_length']
        count = session_length_per_day[date]['count']
        avg_length = total_length / count if count > 0 else 0
        session_length_data.append({'y': date.strftime('%Y-%m-%d'), 'a': avg_length})

    return render_template('admin/stats/stats.html', stats=stats, morris_data=morris_data, page_stats=page_stats_data, session_length_data=session_length_data)


### END STATS AREA

# Home Page
@app.route('/')
def home():

    # Meta Data
    data_object = {'title' : 'Home'}
    meta_data = fetch_meta_data(data_object)

    data_dict = build_data_dict(Topics, articles)
    recent_articles = recently_published(articles, Topics)

    return render_template('index.html', assets=assets, data_dict=data_dict, meta_data=meta_data, recent_articles=recent_articles)

# Single Example
@app.route('/examples/<article_path>')
def example(article_path):
    data_dict = build_data_dict(Topics, articles)
    breadcrumbs = get_breadcrumbs()
    current_url = request.url
    article = None
    article = articles.query.filter_by(path=article_path).first()
    meta_data = fetch_meta_data(article)
    if article:
        example = article
        content = htmlize(example.content)
        table_of_contents = generate_table_of_contents(content)

    return render_template('examples-single.html', breadcrumbs=breadcrumbs, assets=assets, example=example, current_url=current_url, data_dict=data_dict, table_of_contents=table_of_contents, content=content, meta_data=meta_data)

# Single Blog
@app.route('/blog/<blog_path>')
def blogs_single(blog_path):
    data_dict = build_data_dict(Topics, articles)
    breadcrumbs = get_breadcrumbs()
    blog_query = None
    blog_data = None
    blog_query = blogs.query.filter_by(path=blog_path).first()
    meta_data = fetch_meta_data(blog_query)
    if blog_query:
        blog_data = blog_query
        content = htmlize(blog_query.content)
        table_of_contents = generate_table_of_contents(content)

    return render_template('blog-single.html', assets=assets, breadcrumbs=breadcrumbs, blog=blog_data, data_dict=data_dict, table_of_contents=table_of_contents, content=content, meta_data=meta_data)

# Still needs metadata!
# List Topics
@app.route('/topics')
def topics_list():
    data_dict = build_data_dict(Topics, articles)
    return render_template('topics-list.html', assets=assets, data_dict=data_dict)

# Still needs metadata!
# First Level Topic
@app.route('/topics/<first_level_topic_path>/')
def topics_first_level(first_level_topic_path):
    data_dict = build_data_dict(Topics, articles)
    
    return render_template('first-level-topic.html', assets=assets, data_dict=data_dict, topic_path=first_level_topic_path)

# Still needs metadata!
# Second Level Topic
@app.route('/topics/<first_level_topic_path>/<second_level_topic_path>/')
def topics_second_level(first_level_topic_path,second_level_topic_path):
    data_dict = build_data_dict(Topics, articles)
    
    return render_template('second-level-topic.html', assets=assets, data_dict=data_dict, topic_path=first_level_topic_path, sec_level_topic_path=second_level_topic_path)

# Still needs metadata!
# Third Level Topic
@app.route('/topics/<first_level_topic_path>/<second_level_topic_path>/<third_level_topic_path>/')
def topics_third_level(first_level_topic_path,second_level_topic_path, third_level_topic_path):
    data_dict = build_data_dict(Topics, articles)
    
    return render_template('third-level-topic.html', assets=assets, data_dict=data_dict, topic_path=first_level_topic_path, sec_level_topic_path=second_level_topic_path, third_level_topic_path=third_level_topic_path)

# Single Article (Topic)
@app.route('/topics/<first_level_topic_path>/<second_level_topic_path>/<third_level_topic_path>/<article_path>/')
def topic_single(first_level_topic_path, second_level_topic_path, third_level_topic_path, article_path):
    data_dict = build_data_dict(Topics, articles)
    breadcrumbs = get_breadcrumbs()
    current_url = request.url
    article = None
    article = articles.query.filter_by(path=article_path).first()
    meta_data = fetch_meta_data(article)
    related_articles = None
    if article:
        related_articles = find_related_articles(article_path, articles, Topics)
        content = htmlize(article.content)
        table_of_contents = generate_table_of_contents(content)
        if (len(content) > 0):
            reading_time = calculate_reading_time(article.content)

    return render_template('topic-single.html', breadcrumbs=breadcrumbs, assets=assets, article=article, current_url=current_url, data_dict=data_dict, table_of_contents=table_of_contents, content=content, reading_time=reading_time, meta_data=meta_data, related_articles=related_articles)

# List Examples
@app.route('/examples')
def examples():

    # Meta Data
    data_object = {'title' : 'Examples'}
    meta_data = fetch_meta_data(data_object)

    data_dict = build_data_dict(Topics, articles)
    print(data_dict)
    return render_template('examples-list.html', assets=assets, data_dict=data_dict, meta_data=meta_data)

# List Blogs
@app.route('/blog')
def blog():

    # Meta Data
    data_object = {'title' : 'Blog'}
    meta_data = fetch_meta_data(data_object)

    data_dict = build_data_dict(Topics, articles)
    blogs_data = blogs.query.all()

    # Lus door de lijst en formatteer de datum in elk item
    for blog in blogs_data:
        if blog.date:
            # Scheid de tijdzone-informatie
            date_parts = blog.date.split("+")
            date_without_timezone = date_parts[0]

            # Converteer naar een datumobject
            date_object = datetime.strptime(
                date_without_timezone, "%Y-%m-%dT%H:%M:%S")

            # Formateer de datum naar het gewenste formaat
            blog.formatted_date = date_object.strftime("%B %d, %Y")
        else:
            blog.formatted_date = None

    return render_template('blog-list.html', assets=assets, data_dict=data_dict, blogs_data=blogs_data, meta_data=meta_data)

# About
@app.route('/about')
def about():

    # Meta Data
    data_object = {'title' : 'About Us'}
    meta_data = fetch_meta_data(data_object)

    data_dict = build_data_dict(Topics, articles)
    return render_template('about.html', assets=assets, data_dict=data_dict, meta_data=meta_data)

# Contribute
@app.route('/contribute')
def contribute():

    # Meta Data
    data_object = {'title' : 'Contribute to TSH'}
    meta_data = fetch_meta_data(data_object)

    return redirect('topics/collaborate-share/project-management/engage-open-science/contribute-to-tilburg-science-hub/contribute/')

# Search Page
@app.route('/search')
def search():

    # Meta Data
    data_object = {'title' : 'Search'}
    meta_data = fetch_meta_data(data_object)

    data_dict = build_data_dict(Topics, articles)
    return render_template('search.html', assets=assets, data_dict=data_dict, meta_data=meta_data)

# Contributors
@app.route('/contributors')
def contributors():

    # Meta Data
    data_object = {'title' : 'Contributors'}
    meta_data = fetch_meta_data(data_object)

    data_dict = build_data_dict(Topics, articles)
    contributors_list = Contributors.query.all()
    return render_template('contributors-list.html', assets=assets, data_dict=data_dict, contributors_list=contributors_list, meta_data=meta_data)

# Still needs metadata!
# Single Contributor
@app.route('/contributors/<contributor_path>')
def contributor(contributor_path):
    data_dict = build_data_dict(Topics, articles)
    contributor_single = Contributors.query.filter_by(
        path=contributor_path).first()
    
    if contributor_single is None:
        abort(404)
    
    contributions = fetch_contributions_for_the_single_contributor(contributor_single, articles, Topics)

    return render_template('contributors-single.html', assets=assets, data_dict=data_dict, contributor_single=contributor_single, contributions=contributions)

# Redirects
setup_redirects(app)

# Still needs metadata!
# Error Handler 404
@app.errorhandler(404)
def page_not_found(e):
    data_dict = build_data_dict(Topics, articles)
    return render_template('404.html', assets=assets, data_dict=data_dict), 404

if __name__ == '__main__':
    app.run(debug=True)
