---
categories: []
created: '2026-06-20T02:02:12.540707+00:00'
id: overview
modified: '2026-06-20T07:23:14.525030+00:00'
tags:
- documentation
title: WikiKnowledge overview
type: leaf
---

# WikiKnowledge Graph Construction and Question Answering System

[[file:wikiknowledge-logo.svg|WikiKnowledge Logo]]

## Why Wikipedia Thrives While Wikibooks Does Not

### The Anatomy of a Textbook

Writing a book requires building a rigid, logical structure where each subsequent chapter builds directly upon the previous one. Take a look at the layout of a typical textbook:

* **Fractal Hierarchy:** It starts with a brief table of contents that maps out the overall structure. Each chapter then features a detailed outline, and every section follows this same pattern—starting with an introduction and summary to show how it relates to the rest of the book.
* **Logical Progression:** Every chapter follows the scientific method: it begins with a problem statement, describes the method to solve it, and presents results and conclusions. The material is backed by examples, exercises, and clear references.
* **The Structural Graph:** Essentially, each chapter acts as a node in a graph, and the edges represent a strict, sequential flow of information.

Because of this deeply integrated structure, a book requires an "architect"—a single author or a tightly coordinated collective responsible for the entire vision.

### Why Wikibooks Struggles

This rigid requirement is exactly why Wikibooks has not gained as much traction as Wikipedia. The crowd-sourced, decentralized wiki model is fundamentally at odds with the cohesive narrative a textbook demands.

Without a central architect, a book quickly devolves into a disjointed collection of pages rather than a continuous learning path. This structural difference makes Wikipedia excellent for looking up a specific topic, but poor for learning a complex subject from scratch. For example, if you want to learn about machine learning, reading the Wikipedia article will not give you a linear, comprehensive understanding. You will have to manually hop between multiple articles and piece the information together yourself.

### How Wikipedia Manages the Chaos

In contrast, Wikipedia thrives because it is designed to organize assorted pieces of knowledge rather than a single, linear narrative. It features a robust set of tools specifically built to manage the chaos that arises from having no central architect:

* **Wiki links and "What links here" pages** to map relationships between separate ideas.
* **Categories** to group related articles together dynamically.
* **Templates** to standardize how information is presented across the site.

While these tools are highly effective at managing a vast, decentralized web of encyclopedia articles, they simply are not enough to build the strict, step-by-step structure required to write a coherent book.


### Project goal

This project provides a means to build a hierarchical "fractal" knowledge graph over the information distributed among separate markdown files. It uses wiki tools: anchors, categories and reverse links to create a graph of the knowledge, utilizes AI to create overviews for the multi-level **overview layer** that guides the reader through the knowledge, and allows to quickly get a grasp of a specific topic, and dive in deeper if needed. The project also provides a question answering system, which allows to ask questions about the knowledge in the graph, and get answers based on the information in the graph.

### Data organization

Knowledge is stored in "leaf" articles, which have wiki tags and category anchors to make these articles indexable. For each category there is an **overview article**, which is a summary of the category and its relation to other categories. The **overview articles** are also organized in a hierarchical way, where each **overview** has a parent **overview**, and so on. The top-level **overview** is the root of the graph, and it provides an overview of the entire knowledge graph.
Every article can be part of many categories, so there is no strict hierarchical structure, but it is still always possible to go "up".
Combinations of different categories can also have their own **overview articles**, which are summaries of the combined knowledge of the categories. For example, if there are two categories "Rigid body dynamics" and "Computer simulation", there can be an **overview article** "Rigid body dynamics in computer simulation", which is a summary of the knowledge in both categories and their relation to each other, explaining different approaches to building physics simulation engines.

On the physical level, information can be [[storage-abstraction|stored]] in one of two ways: markdown files and an index file, which can be rebuilt from scratch at any time. Another option is a NoSQL database like MongoDB with categories and external references separated into indexable fields.

A typical update cascade looks like this: a leaf article is updated, which triggers an update of the **overview article** of that category, which triggers an update of the parent **overview article**, and so on, up to the root **overview**. This way, the entire graph is always up to date, and the reader can always get a comprehensive understanding of a topic by reading the **overview articles**, and then dive into the leaf articles for more details if needed.

Rewriting of the **overview articles** is done by AI, which allows to quickly update the entire graph without much manual work, but they can have specially marked sections that are maintained by humans. The human-written part acts as the preface in the textbook framework above, defining the main concepts and the structure of the knowledge, while the AI-written part summarizes the articles with references to go deeper. This way, the human can focus on the "architect" part of the book, while the AI takes care of the "content" layer.

There is also a visualization of the graph, which allows users to see the structure of the knowledge and navigate through it.