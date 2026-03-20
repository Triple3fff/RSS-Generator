import sqlite3
conn = sqlite3.connect('data/rss_generator.db')

print('--- Feed configs ---')
for r in conn.execute('SELECT id, title, use_playwright, last_scraped_at FROM feed_configs').fetchall():
    print(r)

print('--- Last 5 scrape logs ---')
for r in conn.execute('SELECT feed_config_id, success, new_items, updated_items, error_message, scraped_at FROM scrape_logs ORDER BY id DESC LIMIT 5').fetchall():
    print(r)

print('--- Items without links ---')
for r in conn.execute('SELECT feed_config_id, title, link FROM feed_items WHERE link IS NULL LIMIT 10').fetchall():
    print(r)
