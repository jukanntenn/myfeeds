{% for submission in submissions %}
#### {{ submission.title }}

UP主: {{ submission.author }}

发布时间: {{ submission.created_at }}

时长: {{ submission.length }}

[点击查看]({{ submission.link }})
{% endfor %}