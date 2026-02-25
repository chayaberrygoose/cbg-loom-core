# printify


This is how you download products from printify. You can use the token in printify_api_token.txt.
```
curl -X GET https://api.printify.com/v1/shops/12043562/products.json --header "Authorization: Bearer $PRINTIFY_API_TOKEN"
```