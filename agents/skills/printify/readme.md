```markdown
# printify


This is how you download products from Printify. Set your token in the `PRINTIFY_API_TOKEN` environment variable and the shop in `PRINTIFY_SHOP_ID`.

```bash
curl -X GET https://api.printify.com/v1/shops/$PRINTIFY_SHOP_ID/products.json --header "Authorization: Bearer $PRINTIFY_API_TOKEN"
```

``` 
