---
layout: page
title: Hello from lk's World
---
{% include JB/setup %}

# Comming soon ...

<div class="content">
<ul class="posts">
  {% for post in site.posts %}
    <li><span>{{ post.date | date_to_string }}</span> &raquo; <a href="{{ BASE_PATH }}{{ post.url }}">{{ post.title }}</a>
    <p>{{ post.excerpt }}</p></li>
  {% endfor %}
</ul>
</div>
