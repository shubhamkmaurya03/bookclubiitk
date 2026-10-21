# Book Club IIT Kanpur: shelf status

Live shelf status for the [Book Club catalogue](https://www.iitk.ac.in/bookclub/catalogue.html).

The club computer reads the library system (Koha) every 2 minutes and, when a book is issued or returned,
replaces the `status` branch with two files, which the workflow here publishes on GitHub Pages:

- `status.json`: for each title with a copy out, `[copies, issued, earliest due date]`, keyed by Koha's record number
- `books.json`: the list of titles in Koha: `[record number, title, author, ISBN, copies]`

They contain no member information. The code that writes them is in
[bookclubiitk/tools/shelf](https://github.com/shubhamkmaurya03/bookclubiitk/tree/main/tools/shelf).
