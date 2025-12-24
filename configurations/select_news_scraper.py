from news_scrapers.pr_newswire import scrape_prnewswire
from news_scrapers.zee_news import scrape_zeenews
from news_scrapers.the_hindu import scrape_thehindu
from news_scrapers.free_press_journal import scrape_freepressjournal
from news_scrapers.business_standerd import scrape_businessstandard
# from news_scrapers.economic_time import scrape_economictimes
# from news_scrapers.live_mint import scrape_livemint
# from news_scrapers.hindustan_times import scrape_hindustantimes
# from news_scrapers.india_tv import scrape_indiatvnews
# from news_scrapers.times_of_india import scrape_timesofindia
# from news_scrapers.et_now import scrape_etnownews
# from news_scrapers.indian_express import scrape_indianexpress



scrapers = {
  "PR_NEWSWIRE": scrape_prnewswire,
  "ZEE_NEWS": scrape_zeenews,
  "THE_HINDU": scrape_thehindu,
  "FREE_PRESS_JOURNAL": scrape_freepressjournal,
  "BUSINESS_STANDARD": scrape_businessstandard,
  "INDIA_TIMES": False,
  "INDIA_TODAY": False,
  "LIVE_MINT": False,
  "INDIA_TV": False,
  "MONEY_CONTROL": False,
  "TIMES_OF_INDIA": False,
  "NEWS18": False,
  "HINDUSTAN_TIMES": False,
  "INDIAN_EXPRESS": False,
  "ET_NOW": False,
  "ECONOMIC_TIMES": False
}
