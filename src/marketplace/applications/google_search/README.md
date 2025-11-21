# Google Custom Search JSON API – Setup

This project uses the **Google Custom Search JSON API** to fetch Google search results in Python.

## 1. Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/).
2. Click **Select Project → New Project**.
3. Give it a name and click **Create**.

## 2. Enable the Custom Search API

1. In your project, go to **APIs & Services → Library**.
2. Search for **Custom Search API**.
3. Click **Enable**.

## 3. Get an API Key

1. Go to **APIs & Services → Credentials**.
2. Click **Create Credentials → API Key**.
3. Copy the generated key.

## 4. Create a Programmable Search Engine (CSE)

1. Go to [Programmable Search Engine](https://programmablesearchengine.google.com/about/).
2. Click **Add** → enter the sites you want to search (or `*` for the entire web).
3. Copy the **Search Engine ID (cx)** from the control panel.
4. Make sure **“Search the entire web”** is enabled if needed.

## 5. Store your credentials in a `.env` file

Create a `.env` file at the root of your project and add:

```
GOOGLE_CUSTOM_SEARCH_API_KEY=your_api_key_here
GOOGLE_CUSTOM_SEARCH_ENGINE_ID=your_search_engine_id_here
```
