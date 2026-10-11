# SPDX-License-Identifier: Apache-2.0
# web-node/Dockerfile
# Ospita SOLO i file statici del web node: il nodo vero (registrazione,
# long-poll, esecuzione task, inferenza WebGPU) gira nel BROWSER del client,
# non qui. nginx:alpine e' piccolo e serve index.html + i moduli ES con i MIME
# giusti.
FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html /usr/share/nginx/html/index.html
COPY join.html /usr/share/nginx/html/join.html
COPY progetto.html /usr/share/nginx/html/progetto.html
COPY join-config.js /usr/share/nginx/html/join-config.js
COPY src /usr/share/nginx/html/src
