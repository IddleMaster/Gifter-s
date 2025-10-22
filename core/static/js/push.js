{% load static %}

<!-- Inyecta la config de Firebase desde settings -->
<script id="fb-config" type="application/json">
  {{ settings.FIREBASE.WEB_CONFIG|json_script:"fb-config" }}
</script>

<!-- Carga el script de push (ESM) -->
<script type="module" src="{% static 'js/push.js' %}"></script>
