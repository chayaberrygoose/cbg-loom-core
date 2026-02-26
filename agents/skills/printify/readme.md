````markdown
# printify


This is how you download products from printify. Set your token in the `PRINTIFY_API_TOKEN` environment variable.
```
curl -X GET https://api.printify.com/v1/shops/12043562/products.json --header "Authorization: Bearer $PRINTIFY_API_TOKEN"
```
````
