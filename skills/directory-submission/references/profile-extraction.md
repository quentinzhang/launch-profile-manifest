# Product Profile extraction

Use this workflow when the source is prose, Markdown, a transcript, pasted website copy, or another unstructured document. The language model performs semantic extraction; the builder only validates and packages the reviewed result.

## Canonical fields

Write only these string fields under `productProfile`:

- Identity: `productName`, `companyName`, `websiteUrl`, `founderName`, `contactEmail`
- Positioning: `tagline`, `shortDescription`, `longDescription`, `categories`, `tags`, `pricing`
- Assets: `logoUrl`, `screenshotUrls`, `demoVideoUrl`
- Social: `twitterUrl`, `linkedinUrl`

Use comma-separated text for `categories` and `tags`, and newline-separated URLs for `screenshotUrls`. Preserve explicitly supplied spelling, capitalization, email addresses, prices, and URLs.

## Evidence statuses

Assign one status to every populated field:

- `explicit`: stated directly in user-provided material.
- `derived`: condensed, reformatted, translated, or composed from explicit facts.
- `inferred`: a reasonable classification or interpretation not directly stated.

Do not put missing fields in `productProfile`. Never infer contact details, prices, claims, asset URLs, social URLs, dates, credentials, legal statements, or quantitative results. “Free trial” is not equivalent to “Free”; a personal email is not automatically the public support address.

For `derived` and `inferred` fields, explain the reasoning and obtain explicit user confirmation. If a required field is absent or conflicting, ask only for that field. The user's original statement confirms the literal facts it contains, but it does not confirm model-written copy or classifications.

## Reviewed packet

Create a JSON packet with this shape after extraction:

```json
{
  "inputType": "unstructured",
  "confirmedByUser": true,
  "source": {
    "type": "user_document",
    "title": "Product notes supplied in chat"
  },
  "productProfile": {
    "productName": "Example Product",
    "websiteUrl": "https://example.com",
    "shortDescription": "Reviewed description",
    "categories": "AI Tools, Productivity"
  },
  "fieldEvidence": {
    "productName": {
      "status": "explicit",
      "confidence": 1.0,
      "evidence": "Our product is called Example Product."
    },
    "shortDescription": {
      "status": "derived",
      "confidence": 0.9,
      "evidence": "Condensed from the reviewed problem and feature paragraphs."
    },
    "categories": {
      "status": "inferred",
      "confidence": 0.8,
      "evidence": "Classified from the described AI workflow and productivity use case."
    }
  }
}
```

For `inputType: "unstructured"`, every populated field needs a matching evidence entry. `confirmedByUser: true` means the normalized values—not merely the source document—were reviewed. Do not store credentials or unrelated document content in evidence excerpts.

## Target preflight

After target selection, compare the packet with each target's `requiredAutofillFields`. Resolve missing required values before delivery. Fields that the site intentionally leaves manual belong in `manualFields`, not in `requiredAutofillFields`.

Final form submission, login, captcha, uploads marked manual, and payment remain human actions even after every field is confirmed.
