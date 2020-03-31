"""
No data dictionary avaliable, but spoke with Land Matrix over email
and got some clarification:

> Deal size is an attribute that the Land Matrix platform calculates to work out the chart and graphs on our global, regional and country pages. It will take the size under contract, or where this is not available the size in operation. Intended size (for an intended deal) is not taken into account hence some rows being 0. It would be better to use the current size under contract, current size in operation or intended size depending on the negotiation status you are looking at.
>
> Country 1,2,3 indicates when there is an export of produce to which country the produce is exported to.

"""

import json
import numpy as np
import pandas as pd
from collections import defaultdict
from dms2dec.dms_convert import dms2dec

deals_df = pd.read_csv('deals.csv', delimiter=';')
investors_df = pd.read_csv('investors.csv', delimiter=';')
involvements_df = pd.read_csv('involvements.csv', delimiter=';')

print('deals', len(deals_df))
print('investors', len(investors_df))
print('involvements', len(involvements_df))

print('='*20)
for col in deals_df.columns:
    print(col)
print('='*20)

# Standardize
standardize = [
    'Negotiation status',
    'Intention of investment'
]
for col in standardize:
    deals_df[col] = deals_df[col].apply(
            lambda v: (v if isinstance(v, str) else '').split('#')[-1])

# Filter to these statuses
statuses = [
    'Intended (Under negotiation)',
    'Indended (Memorandum of understanding)',
    'Concluded (Oral Agreement)',
    'Concluded (Contract signed)'
]
deals_df = deals_df[deals_df['Negotiation status'].isin(statuses)]
print(len(deals_df), 'deals')
print('='*20)

# Adjust deal size
# based on info from above
size_cols = [
    'Deal size',
    'Current size under contract',
    'Current size in operation (production)',
    'Intended size (in ha)',
    'Size under contract (leased or purchased area, in ha)',
    'Size in operation (production, in ha)',
]
def get_size(r):
    sizes = []
    for c in size_cols:
        size = r[c]
        if isinstance(size, str):
            size = float(size.split('#')[-1])
        if not np.isnan(size):
            sizes.append(size)
    return max(*sizes)
deals_df['Size'] = deals_df.apply(get_size, axis=1)

print('Area by target country')
# Check that all deals have only one target country
target_cols = [c for c in deals_df.columns if 'Target country' in c]
for i, r in deals_df.iterrows():
    countries = set(r[c] for c in target_cols if isinstance(r[c], str))
    assert len(countries) == 1
deals_df['Target country'] = deals_df.apply(lambda r: [r[c] for c in target_cols if isinstance(r[c], str)][0], axis=1)
print(deals_df.groupby('Target country')['Size'].sum())
print('='*20)

col = 'Intention of investment'
print(deals_df[col].str.split(', ', expand=True).stack().value_counts())
print('-'*20)
print(deals_df[col].str.split(', ', expand=True).stack().value_counts(normalize=True))
print('-'*20)
print(deals_df[col].value_counts(normalize=True))
print('-'*20)
intents = [
    'Food crops',
    'Livestock',
    'Agriculture unspecified',
    'Non-food agricultural commodities',
    'Biofuels'
]
deals_df['Agriculture'] = deals_df.apply(lambda r: any(i in r[col] for i in intents), axis=1)
print(deals_df['Agriculture'].value_counts(normalize=True))
print('='*20)

col = 'Former land use'
print(deals_df[col].str.split('|', expand=True).stack().value_counts())
print('='*20)

col = 'Former land owner'
print(deals_df[col].str.split('|', expand=True).stack().value_counts())
print('='*20)

col = 'Negative impacts for local communities'
print(deals_df[col].str.split('|', expand=True).stack().value_counts())
print('='*20)

count_cols = [
    'Deal scope',
    'Negotiation status',
    'Operating company: Classification',
    'Presence of land conflicts',
    'Displacement of people',
    'Community consultation',
    'Community reaction',
    'Has export',
    'Has domestic use',
]
for col in count_cols:
    print(deals_df[col].value_counts(normalize=True, dropna=False))
    print('='*20)


# Get lat/lngs for deals
loc_cols = [
    'Location {}: Spatial accuracy level',
    'Location {}: Location',
    'Location {}: Latitude',
    'Location {}: Longitude',
    'Location {}: Facility name',
    'Location {}: Target country',
    'Location {}: Location description',
    'Location {}: Comment on location'
]
deal_coords = {}
for i, row in deals_df.iterrows():
    id = row['Deal ID']
    deal_coords[id] = []
    for i in range(1, 22):
        lat = str(row['Location {}: Latitude'.format(i)]).replace(',', '.')
        lng = str(row['Location {}: Longitude'.format(i)]).replace(',', '.')

        try:
            lat = float(lat)
        except ValueError: # probably in degree minute seconds (DMS) format
            lat = dms2dec(lat)
        try:
            lng = float(lng)
        except ValueError: # probably in degree minute seconds (DMS) format
            lng = dms2dec(lng)

        country = row['Location {}: Target country'.format(i)]
        accuracy = row['Location {}: Spatial accuracy level'.format(i)]
        if np.isnan(lat):
            break
        deal_coords[id].append({
            'coords': (lat, lng),
            'country': country,
            'accuracy': accuracy,
            'agriculture': row['Agriculture'],
            'size': row['Size']
        })

# Check that all deals have only one investor country
# "Operating company" does not appear to mean investor company?
importers = defaultdict(list)
sizes = defaultdict(int)
target_cols = ['Country 1', 'Country 2', 'Country 3']
tn_deals_df = deals_df[deals_df['Deal scope'] == 'transnational']
ddf = deals_df # tn_deals_df or deals_df
for i, r in ddf.iterrows():
    id = r['Deal ID']
    countries = set(r[c] for c in target_cols if isinstance(r[c], str))
    for c in countries:
        sizes[c] += r['Size']
        for deal in deal_coords[id]:
            if deal['agriculture']:
                importers[c].append(deal)
countries = sorted(sizes.keys(), key=lambda k: sizes[k], reverse=True)
for c in countries:
    print(c, sizes[c])
print('='*20)

with open('importers.json', 'w') as f:
    json.dump(importers, f)

# Breakdowns by country (top five)
for c in countries[:5]:
    print('\n****', c, '****')
    df = deals_df[(deals_df[target_cols] == c).any(axis=1)]
    print(len(df), 'deals')
    for col in count_cols + ['Agriculture']:
        print(df[col].value_counts(normalize=True, dropna=False))
        print('~'*20)
    print(df.groupby('Target country')['Size'].sum())
    print('='*20)