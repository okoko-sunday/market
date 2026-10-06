# End-to-end demonstration

1. Start both products and configure the dealer worker with the marketplace receiver URL and matching secret/source.
2. Publish a dealer car. The receiver returns `202`; run/observe the marketplace worker. Staff sees the listing as **Pending review**, while public search does not.
3. Sign in at `/staff/login`, open Review, and approve it. It becomes public with the projected dealer identity.
4. Change the dealer price. After delivery, the public price changes and moderation remains approved.
5. Mark it Sold. The detail page may remain with a Sold badge, but Available search and request creation exclude it.
6. Unpublish it. All public surfaces and the sitemap exclude it and the retained record becomes Withdrawn.
7. Republish. It returns to Pending review and requires a new approval.
8. Run `python manage.py reconcile_source dealer-platform`; a complete snapshot repairs missed source versions without resetting moderation.
