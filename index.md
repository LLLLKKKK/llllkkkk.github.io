---
layout: page
title: Hello from lk's World
---
{% include JB/setup %}

<div class="span8">
<ul class="posts">
  {% for post in site.posts %}
    <li><h1><span>{{ post.date | date_to_string }}</span> &raquo; <a href="{{ BASE_PATH }}{{ post.url }}">{{ post.title }}</a></h1>
    <p>{{ post.excerpt }}</p></li>
  {% endfor %}
</ul>
</div>
