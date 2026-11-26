# Ebay Lister User Guide

Ebay Lister helps you list items on eBay quickly. You set up a **template** once for each kind of item you sell (for example "Pokemon card"), then each new listing only needs photos, a price and the few details that change, like the card's name and number.

New listings go into a **queue** first, so you can photograph and describe a whole batch of items, then send them all to eBay in one go.

> This guide starts with a five-minute quick start. The later chapters explain each part of the app in more detail. Use them when you need them.

## Quick start

You can try the app before connecting it to eBay. Until you connect, everything you create waits safely in the queue.

1. **Open the app.** On a Mac, open **Ebay Lister** from your Applications folder. On Windows, open the **Ebay Lister** folder and double-click **Ebay Lister.exe**. The first time, your computer may warn you about the app; see "Opening the app for the first time" below.
2. **Pick a template.** On the **List Item** tab, choose **Pokemon card** (or **Patch**) under *Use template*. Both are starter templates you can change to suit you.
3. **Add photos.** Drag photos from Finder or File Explorer onto the photo area, or click it to choose files. Use the arrow buttons under a photo to change the order.
4. **Fill in the details.** Type the card's name, number, set and rarity, for example *Charizard*, *4/102*, *Base Set* and *Holo Rare*, and a price. Watch the **Title** fill in as you type. The counter under it shows how close you are to eBay's 80-character limit. You can also click into the title and reword it for this one item.
5. **Click Add to queue.** The item is saved instantly and the form clears for the next one.
6. **Connect eBay** when you're ready (see "Connecting to eBay"), then go to **Items Database** and click **List all queued**.

That's the whole routine: pick a template, add photos, fill in a few boxes, queue, repeat. List the batch when you're done.

## Opening the app for the first time

The app isn't signed by Apple or Microsoft, so your computer is cautious the first time you open it. You only need to do this once.

**Mac (macOS 15 Sequoia and later):** double-click the app once and close the warning. Open **System Settings › Privacy & Security**, scroll down to the message about Ebay Lister, and click **Open Anyway**.

**Mac (macOS 14 and earlier):** right-click (or Control-click) the app, choose **Open**, then click **Open** again.

**Windows:** if you see "Windows protected your PC", click **More info**, then **Run anyway**. Keep the whole Ebay Lister folder together; the program needs the files next to it.

## A tour of the app

The window has five tabs. You can also switch between them with Cmd+1 to Cmd+5 on a Mac, or Ctrl+1 to Ctrl+5 on Windows.

| Tab | What it's for |
|---|---|
| **List Item** | Create a new listing: choose a template, add photos, fill in the details and click Create. |
| **Items Database** | Everything you've queued or listed. Bulk-list the queue, mark items sold, track profit and sync sales from eBay. |
| **Templates** | Set up your templates: title and description patterns, variables, eBay category, package size, standard photos and policies. |
| **Helpful Links** | Shortcuts to your eBay orders, active listings, time away and developer keys. |
| **Settings** | Your eBay keys, connecting to eBay, and the app's appearance (dark, light or match your computer). |

## Templates and variables

A **template** holds everything that's the same for one kind of item:

* the title and description, with blanks to fill in;
* condition notes and item specifics (Brand, Model, Color and so on);
* the eBay category, condition, default price, quantity and Best Offer setting;
* the package weight and size, used for shipping;
* up to three **standard photos** added to every listing, such as a photo of your shipping box or a "what's included" picture;
* your business policies (shipping, payment, returns) and ship-from location.

You start with three templates: **Patch** (embroidered and other sew-on or iron-on patches), **Pokemon card** (single ungraded cards) and **Blank template**, an empty starting point. Change them to suit how you sell, or duplicate one to make a new template.

### Variables: the blanks you fill in

**Variables** are the parts that change from item to item. Each variable becomes a text box on the List Item tab. Wherever you write its name in curly braces, like `{MODEL}`, the app puts in what you typed.

For example, with variables called CARD_NAME and CARD_NUMBER:

```
Title:     Pokemon {CARD_NAME} {CARD_NUMBER} TCG Card
Specifics: Card Name: {CARD_NAME}
```

Typing *Charizard* and *4/102* on the List Item tab gives the title "Pokemon Charizard 4/102 TCG Card".

* **Adding a variable:** in the *Variables* section of the Templates tab, click **Add…**, give it a name and, if you like, a default value. Tick *Multi-line text box* for longer notes.
* **Names** use letters, numbers and underscores, and start with a letter. CAPITALS are easiest to spot, for example CARD_NAME or CONDITION_NOTES.
* **Putting it in the text:** click where you want it in the title or description, then use **Insert {NAME} at cursor**. Or just type it.
* **Required boxes:** variables used in the **title** must be filled in before you can create the item. They're marked with a star on the List Item tab. Others can be left blank, and an item-specifics line that ends up empty is left out.
* **Renaming a variable** updates it everywhere in the template.
* **Typos are caught:** if you write `{CARD_NAM}` and there's no such variable, the title hint turns red and **Validate** tells you.

### Item specifics

Item specifics are the "Brand", "Size", "Card Name" details buyers filter by. Write one per line as `Name: value`, and separate several values with `|`.

Click **Suggest item specifics from eBay…** under the box to see the specifics eBay wants for the template's category, with lists of the values eBay accepts. Required ones are marked with a star. Pick or type a value for the ones you want; values can be variables, like `{CARD_NAME}`. Click **Apply** to add them to the box. Leaving a box empty leaves that specific out. This only needs your eBay keys in Settings, not a connected account.

### Choosing what the List Item form shows

The **List Item form** section of a template decides which fields appear when you list an item with it, and whether you can change them for that one item:

| Setting | What it does |
|---|---|
| **Hidden** | Not on the form. The template's value is used. |
| **Show** | On the form so you can check it, but it can't be changed there. |
| **Edit** | Starts with the template's value, with your variables filled in, and you can change it for that one item. |

You can choose this for the title, description, condition notes, item specifics, condition, card condition, package weight and size, quantity and Best Offer. New templates let you edit the title, item specifics and package, and show the description and condition notes.

### Managing templates

Use the buttons next to the template name at the top of the Templates tab:

* **New…** makes a fresh template from the defaults.
* **Duplicate…** copies the current template, including its variables and photos. This is the quickest way to set up a similar product.
* **Rename…** and **Delete** do what they say. Deleting a template doesn't affect items you've already queued or listed.

Click **Save template** (Cmd+S or Ctrl+S) when you're done. **Revert** throws away unsaved changes. If you switch to another template with unsaved changes, the app asks whether to save them.

### Category, policies and location

These settings are only needed when an item is actually sent to eBay, so you can queue items before you've finished them.

* **Category:** click **Suggest…** to search eBay's categories by keyword, then **Use selected category**. The conditions you can choose depend on the category.
* **Card condition:** for trading cards such as Pokemon singles (category 183454), eBay requires the card's condition for ungraded cards: Near Mint or Better, Lightly Played, Moderately Played or Heavily Played. Set **Condition** to *Used - very good (trading cards: Ungraded)* and choose the **Card condition**. Leave it on *(not a trading card)* for everything else.
* **Business policies and location:** after connecting to eBay, click **Load policies & locations from eBay**, then pick your shipping, payment and return policies. If you don't have a ship-from location yet, type your ZIP code and click **Create location**.

## Listing an item

On the **List Item** tab:

1. **Use template:** choose the template. The line next to it shows how many variables and standard photos it has. **Edit template…** jumps to it on the Templates tab.
2. **Photos:** drag photos in or click to browse. eBay allows up to 24 photos per listing, including the template's standard photos. Click a thumbnail to preview it; double-click for full size, and use the arrow keys to flip through.
3. **SKU:** your own reference number for the item. Leave it blank and one is made for you, or click **Generate**.
4. **Price (USD):** starts at the template's default price.
5. **Variables:** fill in the boxes. Starred ones are required.
6. **Listing:** check the title and the other fields your template shows (see "Choosing what the List Item form shows"). Text fields follow your variables as you type. Once you change one by hand, your version is kept; **Reset** goes back to the template's text. For item specifics, **Suggest from eBay…** offers eBay's suggestions for the item. If the package weight and size are shown, they start with the template's and you can change them for an item that's bigger or heavier.
7. **When I click Create:** choose **Add to queue** (recommended) or **List right away**.
8. Click **Validate** to check for problems without creating anything, or click the Create button (its label matches your choice in step 7).

**Clear form** (Cmd+N or Ctrl+N) starts over.

## The queue and bulk listing

**Add to queue** saves the item, with copies of its photos, the moment you click. Nothing goes to eBay yet, so it's fast and works without an internet connection. You can safely move or delete the original photos afterwards.

To send queued items to eBay, open the **Items Database** tab. Queued items have their own section.

* **List all queued** sends every queued item (also **File › List All Queued Items…**, or Cmd+L / Ctrl+L).
* **List selected** sends just the items you've selected. Hold Cmd or Ctrl (or Shift) to select several.
* **Edit queued listing…** changes an item's title, description or price before it's listed.
* **Remove from queue** deletes a queued item you no longer want.

Good to know:

* When a queued item is listed, it uses its template's **current** category, condition, package size, policies and location. So you can fix a template after queueing and every waiting item picks up the change. Anything you changed on the List Item form for that item, like a bigger package, is kept and wins over the template.
* The title and description were filled in when you queued the item. Use **Edit queued listing…** to change them.
* If an item fails (for example, a missing policy), it stays in the queue with the reason shown. Fix the problem and list it again.

### What "List right away" does

When an item is listed, the app uploads its photos to eBay, creates the item with its condition, specifics and package size, and creates a Buy It Now, Good 'Til Cancelled offer with your price, category, policies and location. It then publishes the listing.

If **Publish listings immediately** is turned off in Settings, the offer is created but not published. That's useful for checking listings on eBay before they go live.

## Items Database and sales

The **Items Database** tab lists everything you've created. Active listings are at the top, then the queue, then unpublished, sold and ended items.

* **Search** filters the list. Click a column heading to sort by it. If the window is too small, scroll the whole tab.
* The **Activity log** shows what the app is doing while it bulk-lists or syncs, item by item. It's the same log as on the List Item tab.
* Select an item to see its details at the bottom. Double-click the eBay column, or click **Open on eBay**, to see the listing in your browser. **Copy link** copies its address.
* **Mark items sold** with the sold date, the price, and where it sold. Choose *Other* for items you sold somewhere other than eBay.
* **Profit** is the sold price minus eBay's fees and your cost. Enter your cost, then click **Calculate profit**.
* **Sync with eBay** (Cmd+R or Ctrl+R) checks your listings on eBay. It updates which items are still active, sold or ended, and fills in sold prices, dates and eBay's actual fees from your orders. It never overwrites a profit you typed yourself.
* **Export CSV…** saves the list as a spreadsheet file you can open in Excel or Numbers.
* **Remove from database** only deletes the record in this app. It doesn't end the eBay listing.

## Connecting to eBay

The app talks to eBay through eBay's official developer tools, so you need a free eBay developer account first. You only do this once.

1. Go to **developer.ebay.com** and sign in with your eBay account. (The **Helpful Links** tab has a shortcut.)
2. Under **Application Keys**, copy the **App ID** and **Cert ID** for *Production*.
3. Under **User Tokens**, create a **RuName**. eBay uses this name to send you back after you sign in.
4. In the app, open **Settings**, choose *Production*, paste the three values, and click **Save settings**.
5. Click **Connect to eBay…**. Your browser opens eBay's sign-in page. Sign in and click **Agree**.
6. You'll land on a page, which may look blank or show an error. That's expected. Copy the **full address** from your browser's address bar and paste it into the app.
7. Settings now shows **Connected to eBay**. Go to **Templates** and click **Load policies & locations from eBay**.

The app asks eBay for permission to create listings, read your account's policies, and read (not change) your orders for sales sync. You can click **Disconnect** at any time.

> *Sandbox* is eBay's practice area for developers. Listings there aren't real. Use *Production* to sell.

## Settings and appearance

* **eBay:** your keys, the connection status and the *Publish listings immediately* option.
* **Appearance:** *Dark* (the default), *Light*, or *Match macOS / system* to follow your computer's setting. Restart the app to apply a change.

## Keyboard shortcuts

On a Mac use Cmd; on Windows use Ctrl.

| Shortcut | Action |
|---|---|
| Cmd/Ctrl + 1 to 5 | Switch tabs (List Item, Items Database, Templates, Helpful Links, Settings) |
| Cmd/Ctrl + N | New item (clears the List Item form) |
| Cmd/Ctrl + S | Save the template you're editing |
| Cmd/Ctrl + L | List all queued items |
| Cmd/Ctrl + R | Sync sales with eBay |
| Cmd + , | Settings (Mac) |

## Your data and backups

Everything the app knows lives in one folder on your computer. Use **File › Open Data Folder** to find it.

| Computer | Folder |
|---|---|
| Mac | the hidden *.ebay_lister* folder in your home folder |
| Windows | *Ebay Lister* inside your AppData\Roaming folder |

It holds your settings and eBay sign-in, your templates, the Items Database, and copies of standard and queued photos.

* **Back up** by copying the whole folder somewhere safe. To restore, quit the app and copy it back.
* **Updating the app** never touches this folder, so your templates and history carry over.
* Your eBay keys are stored in this folder. Don't share it with anyone.

## Troubleshooting

| Problem | What to do |
|---|---|
| The Create button says *Add to queue* even though I chose *List right away* | eBay isn't connected yet. Connect it on the Settings tab. |
| A queued item failed to list | Select it in Items Database to read the reason. It's usually a missing category, policy or location on the template. Fix the template, then list it again. |
| eBay says a card condition is required | Choose a **Card condition** on the template (or on the List Item form, if the template lets you edit it). |
| "Title is too long" | eBay allows 80 characters. Shorten the template's title or the value you typed. |
| The title hint is red on the Templates tab | The title uses a `{NAME}` that isn't one of the template's variables, or it's too long. |
| Can't drag photos into the app | Click the photo area to choose files instead. |
| Connecting to eBay fails | Check the App ID, Cert ID and RuName for typos and that *Production* is selected. Make sure you paste the whole address of the page you landed on. |
| Sign-in expired | Click **Connect to eBay…** again. |
| The app closes or shows an error | Use **Help › Open Error Log** and send the file to whoever set the app up for you. |

You can open this guide at any time from **Help › User Guide**.
