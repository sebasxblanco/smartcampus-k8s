# Frontend: nginx sirve la página y reenvía /api/ al backend.
# La dirección del backend llega en BACKEND_URL: la imagen oficial de nginx
# sustituye las variables de /etc/nginx/templates/*.template al arrancar.
FROM nginx:alpine

COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY index.html app.js /usr/share/nginx/html/

ENV BACKEND_URL=http://backend:8000

EXPOSE 80
