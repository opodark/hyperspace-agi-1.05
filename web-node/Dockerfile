# SPDX-License-Identifier: Apache-2.0
# web-node/Dockerfile
# Ospita SOLO i file statici del web node: il nodo vero (registrazione,
# long-poll, esecuzione task, inferenza WebGPU) gira nel BROWSER del client,
# non qui. nginx:alpine e' piccolo e serve index.html + i moduli ES con i MIME
# giusti.
FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY *.html /usr/share/nginx/html/
COPY join-config.js /usr/share/nginx/html/join-config.js
COPY src /usr/share/nginx/html/src
COPY assets /usr/share/nginx/html/assets
