---
layout: page
title: Hello from lk's World
---
{% include JB/setup %}

<ul class="posts">
  {% for post in site.posts %}
    <li><h1><span>{{ post.date | date_to_string }}</span> &raquo; <a href="{{ BASE_PATH }}{{ post.url }}">{{ post.title }}</a></h1>
    </li>
    <p>{{ post.excerpt }}</p> {{ ## fix code block ...}}
  {% endfor %}
</ul>
