# The Commercial Brief

A free, installable phone/desktop news dashboard for UK and global business intelligence, industries, supermarkets, AI, commercial finance and commodity-market risks. No login, API key or paid subscription needed.

## Publish to GitHub Pages
1. Create a **new public repository** on GitHub (for example `the-commercial-brief`).
2. Upload **all** files and folders from this project to the repository root, including the hidden `.github/workflows/update.yml` folder and the existing `data/news.json`. This is a separate app — do not replace the files in your recipe or golf apps.
3. Under **Settings → Pages → Build and deployment**, choose **Deploy from a branch**, branch `main`, folder `/ (root)`, and **Save**.
4. Under **Actions → Refresh business and commodity news**, select **Run workflow** to fetch current articles and monthly benchmarks immediately. After that, GitHub attempts to run it every four hours; scheduled runs can be delayed by GitHub.
5. Visit `https://YOUR-USERNAME.github.io/the-commercial-brief/`. On iPhone, Safari's **Share → Add to Home Screen** gives it an app-style icon.

## How it works
- The GitHub Actions job updates `data/news.json` by reading Google News RSS feeds and BBC RSS, keeping source headlines and publisher links. No claim is made that the editorial selection is human-curated.
- It attempts to read the official **World Bank Pink Sheet monthly Excel dataset** for international market benchmarks. If the source is unavailable, previously verified values remain and keep their source month. Beef, eggs, dairy, pork and other UK-specific categories link out to AHDB or other relevant public UK data rather than inventing prices.
- News cards include **Commercial question** prompts about potential implications; these prompts are not verified impacts.
- The **Commercial finance** desk looks for finance business partnering, FP&A, pricing, promotional effectiveness, revenue management, forecasting and profitability.
- The **Commodities** desk tracks market news as well as benchmark prices: supply shocks, disease outbreaks, harvests, weather, availability, legislation, logistics and emerging risks. Public benchmark prices remain supplementary.
- Every article has a **Quick Summary** button. When article text is publicly accessible, the scheduled GitHub action extracts a short lead and up to three key points. Otherwise, a sufficiently detailed **publisher preview** can be used. This is extractive, not a generative AI summary, and it is labelled as automatic source-based material; read the original before acting on important details. If no reliable text can be retrieved, the app says so rather than inventing points. Paywalled material is not bypassed.
- The source-based summariser requires no API key or subscription. `scripts/quick_summaries.py` handles accessible article text, and `scripts/update_news.py` includes both targeted Google News searches and selected publisher RSS feeds.
- Bookmarks are stored **on the current device** only, using browser local storage.
- Live price headlines are **not** real-time trading quotes. World Bank data are monthly, generally in USD. Actual costs are affected by exchange rates, contracts, specifications and lead times.
- The website works without an app store. Public repositories and GitHub Pages mean the code and saved JSON news headlines are public; no company data should be added.

## Troubleshooting
- **Outdated news:** run the workflow manually in the Actions tab; confirm the workflow can write repo contents under Settings → Actions → General → Workflow permissions.
- **No Quick Summary for an article:** publisher content may be restricted or supplied only as a headline. Open the source link for more detail.
- **No commodity prices:** the external World Bank spreadsheet may have changed format or be temporarily unavailable. UK market links still work. The updater never fabricates price changes.
- **White screen:** check you uploaded `index.html` in the root, and `data/news.json` in the `data` folder. Upload the complete folder structure, not just `index.html`.
- **Blank article list:** switch the recency filter to 'All available'.

## Sources
- [CFO Dive finance RSS](https://www.cfodive.com/feeds/news/)
- [The Grocer RSS](https://www.thegrocer.co.uk/34272.rss)
- [BBC News business RSS](https://feeds.bbci.co.uk/news/business/rss.xml)
- [Google News RSS search](https://news.google.com/)
- [World Bank commodity markets](https://www.worldbank.org/en/research/commodity-markets)
- [AHDB agriculture and food market data](https://ahdb.org.uk/get-the-latest-market-data-prices-and-analysis)