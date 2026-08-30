# Features Status

Static GitHub Pages site for the `סטטוס פיצ'רים` card.

## What it does

- Opens directly as HTML from GitHub Pages
- Accepts a business ID (`ח.פ`)
- Shows one final status per feature
- Ignores `כפילות`
- Prefers `בוצע` if mixed statuses exist for the same feature

## Google-hosted API option

This repo includes a ready Google Apps Script endpoint under:

```text
google_apps_script/
```

That is the recommended way to keep the sheet private while letting the public page fetch live data.

### Deploy it in Google

1. Open Google Apps Script
2. Create a new project
3. Copy `google_apps_script/Code.gs`
4. Copy `google_apps_script/appsscript.json`
5. Deploy as a Web App
6. Set access to anyone who should use the public page
7. Copy the deployed Web App URL

### Connect the page

Edit `config.js` and set:

```js
window.FEATURE_STATUS_CONFIG = {
  apiBaseUrl: "https://script.google.com/macros/s/YOUR_DEPLOYMENT_ID/exec",
  apiMode: "jsonp"
};
```

The Google web app accepts:

```text
?customer_id=516056884
```

And return JSON like:

```json
{
  "ok": true,
  "customer_id": "516056884",
  "business_names": ["Example Business"],
  "found_count": 2,
  "missing_count": 4,
  "services": [
    {
      "key": "sms",
      "label": "SMS",
      "found": true,
      "entry_count": 1,
      "entries": [
        { "status": "בוצע" }
      ]
    }
  ]
}
```

## Direct page URL

After GitHub Pages is enabled, the site opens from:

```text
https://nimbusupport.github.io/features_services/
```
