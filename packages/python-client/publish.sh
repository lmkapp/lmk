#!/bin/bash

pnpm readme:npm

trap "pnpm readme:git" EXIT

VERSION=$(cat package.json | jq -r .version)

echo VERSION $VERSION

TAG=$( [[ $VERSION =~ -([a-z]+)[0-9]+$ ]] && echo ${BASH_REMATCH[1]} || echo latest )

echo pnpm publish --access public --no-git-checks --tag $TAG
