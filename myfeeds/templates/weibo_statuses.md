{% for status in statuses %}
*{{ status.screen_name }}@{{ status.created_at }}*

> {{ status.text}}

{% if "retweeted" in status %}
>> *{{ status.retweeted.screen_name }}@{{ status.retweeted.created_at }}*

>> {{ status.retweeted.text}}

[点击查看]({{ status.link }})
{% endif %}
{% endfor %}