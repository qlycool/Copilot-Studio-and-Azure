---
title: Azure AI Search
date: 2023-10-06
description: >
  Used to build a rich search experience over private, heterogeneous content in web, mobile, and enterprise applications.
categories: [Azure]
tags: [docs, ai-search]
weight: 3
---

Azure AI Search (formerly known as "Azure Search") is a cloud search service that gives developers infrastructure, APIs, and tools for building a rich search experience over private, heterogeneous content in web, mobile, and enterprise applications.

Search is foundational to any app that surfaces text to users, where common scenarios include catalog or document search, online retail apps, or data exploration over proprietary content. When you create a search service, you'll work with the following capabilities:

* A search engine for full text and vector search over a search index containing user-owned content
* Rich indexing, with lexical analysis and optional AI enrichment for content extraction and transformation
* Rich query syntax for vector queries, text search, fuzzy search, autocomplete, geo-search and more
* Programmability through REST APIs and client libraries in Azure SDKs
* Azure integration at the data layer, machine learning layer, and AI (Azure AI services)

![Imagen arquitectura Azure Cognitive Search](https://learn.microsoft.com/en-us/azure/search/media/search-what-is-azure-search/azure-search-diagram.svg)

**Copilot Studio and Azure Labs** uses Azure AI Search to serve an index of vectorized content, that will be used by our LLM (ChatGPT) to respond to user's query.

Learn more at the official documentation: [What is Azure AI Search?](https://learn.microsoft.com/en-us/azure/search/search-what-is-azure-search).

Learning Path:[Implement knowledge mining with Azure AI Search](https://learn.microsoft.com/en-us/training/paths/implement-knowledge-mining-azure-ai-search/)
