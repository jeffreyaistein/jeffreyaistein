"""
Jeffrey AIstein - KOL Style Dataset Configuration

Default KOL handles for style analysis.
Source: KOLSCAN.io top traders research.
"""

# Top 100 KOL handles for style dataset collection
# Organized by tier from original research
KOL_HANDLES = [
    # S-Tier (Market Movers)
    "blknoiz06",      # Ansem - 788K followers
    "MustStopMurad",  # Murad - 737K followers
    "HsakaTrades",    # Hsaka - 605K followers

    # A-Tier (High Influence)
    "Cented7",        # Cented - 467K
    "ramonos",        # Ram - 182K
    "Cupseyy",        # Cupsey - 186K
    "MarcellxMarcell",# Marcell - 140K
    "CookerFlips",    # Cooker - 132K

    # B-Tier (Active Traders)
    "Chairman_DN",    # Chairman - 42K
    "vibed333",       # DV - 29K
    "Latuche95",      # Latuche - 28K
    "exitliquid1ty",  # unprofitable - 25K
    "jijo_exe",       # Jijo - 24K
    "OnlyLJC",        # LJC - 43K
    "bandeez",        # Bandit - 17K

    # C-Tier (Micro-Influencers)
    "YokaiCapital",   # Yokai - 17K
    "0xkitty69",      # Kitty - 17K
    "radiancebrr",    # Radiance - 7.5K
    "Solanadegen",    # Solana degen - 5K
    "chestererer",    # Chester - 3.7K
    "10xJDOG",        # JADAWGS - 2.2K

    # Additional KOLs from research
    "theunipcs",      # Bonk Guy
    "wrennounced",    # Solana ecosystem
    "zachxbt",        # Blockchain investigator
    "orangie",        # Active trader
    "a1lon9",         # Pump.fun co-founder

    # Extended list to reach 100
    # Solana ecosystem voices
    "solaborneoff",
    "0xMert_",
    "TokeisYuki",
    "zaborofficial",
    "CryptoGodJohn",
    "DegenSpartan",
    "aixbt_agent",
    "wassielawyer",
    "Dynamo_Patrick",
    "notthreadguy",
    "ShardiB2",
    "OvermindAI_",
    "WhalePanda",
    "AltcoinGordon",
    "CryptoFinally",
    "degaborneoff",
    "CryptoWendyO",
    "CryptoKaleo",
    "IamNomad",
    "CryptoCapo_",

    # Meme coin traders
    "BullishBros",
    "CryptoMessiah",
    "ColdBloodShill",
    "gainzy222",
    "CryptoNoob",
    "trader1sz",
    "InvestingGhost",
    "CryptoGargs",
    "CryptoIslands",
    "bobbyaxelrod",

    # Solana DeFi
    "orca_so",
    "JupiterExchange",
    "RaydiumProtocol",
    "phantom",
    "marginlounge",
    "solendprotocol",

    # Active trenches voices
    "pump_lounge",
    "soldogdev",
    "tradingdata_",
    "alphaterminal_",
    "solana_devs",
    "wikisolana",
    "SolanaFloor",
    "SolanaLegend",
    "SolanaDaily",
    "TheSolanaDaily",

    # Crypto Twitter influencers
    "CryptoDonAlt",
    "neblobes",
    "Pentosh1",
    "inversebrah",
    "EmperorBTC",
    "SmartContracter",
    "CredibleCrypto",
    "CryptoBull",
    "CryptoVince_",
    "CryptoYoddha",

    # Additional voices
    "degenfranc",
    "CryptoHayes",
    "VirtualBacon",
    "BasedEnjoyer",
    "CryptoGems555",
    "BrokkrFinance",
    "CryptoJobs",
    "SolanaChads",
    "cryptoairdrop",
    "degengoddess",

    # Trading focused
    "CryptoJelleNL",
    "CryptoTony",
    "CryptoMichNL",
    "altcoinpsycho",
    "blaboratecap",
    "TheMoonCarl",
    "CryptoRand",
    "CryptoFaibik",
    "trader0xPunk",
    "cryptowzrd",
]

# Ensure exactly 100 handles
assert len(KOL_HANDLES) == 100, f"Expected 100 handles, got {len(KOL_HANDLES)}"

# Tweets to collect per handle
TWEETS_PER_USER = 20

# Expected total
EXPECTED_TWEETS = len(KOL_HANDLES) * TWEETS_PER_USER  # 2000
