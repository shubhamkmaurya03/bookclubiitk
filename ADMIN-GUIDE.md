# Admin guide for coordinators

You can update the website without touching any code: blog posts, the team, past teams, rules, timings,
the magazine and the home page text.

## First time: get access (about 5 minutes)

1. **Make a GitHub account** at https://github.com/signup if you don't have one, and turn on
   two-factor authentication (*Settings → Password and authentication*).
2. **Ask the current admin to add you** as a collaborator on the repository, and accept the email invite.
3. **Create an access token** (this is your password for the admin panel):
   - Go to https://github.com/settings/tokens → *Generate new token* → **Generate new token (classic)**.
   - Note: `Book Club admin`. Expiration: **90 days** (make a new one when it expires).
   - A classic token can reach every repository of your account, so delete it on that page when your tenure
     ends, and never use it anywhere except the admin panel.
   - Tick the **`repo`** box only, then *Generate token*.
   - Copy the token (it starts with `ghp_`). GitHub shows it only once. Treat it like a password and never share it.

## Making a change

1. Open **https://shubhamkmaurya03.github.io/bookclubiitk/admin/**
2. Click **Sign In Using Access Token** and paste your token. (The "Sign In with GitHub" button is not set up.)
3. Pick what to edit:
   - **Blog posts:** *New Blog post*, or open an existing one.
   - **Club pages → Team:** current coordinators and secretaries, and past teams.
   - **Club pages → Mellifluous:** add a new edition at the **top** of the list.
   - **Club pages → Rules / Timings, contact & home page.**
4. Click **Save**. The website updates in about **2 minutes**. Refresh https://shubhamkmaurya03.github.io/bookclubiitk/ to check.
5. To put the change on **iitk.ac.in**, tell the person with the club's WinSCP login (see README, "Publishing to iitk.ac.in").

## Tips

- **Photos:** upload normal phone photos. They are shrunk and their location data is removed automatically.
  Team photos look best as portraits with the face near the top.
- **Names are sorted A–Z** on the website, so the order you type them in doesn't matter. People without a photo
  are shown with their initials.
- **Blog text:** use the toolbar for **bold**, *italics*, links and quotes. A paragraph written entirely
  inside “curly quotes” becomes a large pull quote.
- **Not ready yet?** Tick *Hide from the website (draft)* on a blog post.
- **Made a mistake?** Every save is recorded. Ask the admin to undo it from the repository history.

## End of tenure

1. In **Team**, add a new entry under **Past teams** (for example `2025-26`) and move the outgoing
   coordinators and secretaries into it.
2. Replace the current team with the new one.
3. The admin removes outgoing coordinators from the repository. Outgoing coordinators should delete
   their token at https://github.com/settings/tokens.

## Safety

- Use the admin panel on your own device. On a shared computer, use the menu → *Sign Out* when done.
- Only people added to the repository can make changes, and every change shows who made it.
- Everything saved is **public** on GitHub, even drafts. Never put phone numbers, roll numbers or other
  private details in the content.
