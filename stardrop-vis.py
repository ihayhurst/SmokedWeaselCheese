#!/usr/bin/env python3
# coding: utf-8
"""Parse  Optibrium-Stardrop Flexlm style log file.
   Show graphics of useage and availability of license """
import re
import argparse
import sys
import json
import datetime
import functools
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.dates import date2num
import seaborn as sns
#import ADlookup as ad

# Set ISO 8601 Datetime format e.g. 2020-12-22T14:30
DT_FORMAT = "%Y-%m-%dT%H:%M"


def log_parse(original_log):
    """Take logfile trim off hash
    Keep only the events we're interested in"""
    grabbag = [
        "License_released",
        "License_granted",
        "Purging_license",
        "License_refused",
    ]

    for line in original_log:
        data = re.split("#", line.strip("\n"))
        data[0] = data[0][12:]  # LOG:stuffffUSERNAME username occurs 12 chars
        if len(data) > 4: # License_granted now has  version number Remove if present
            data.pop(2)

        if [i for i in grabbag if i in data[1]]:
            yield data
        else:
            continue


def readfile_to_dataframe(**kwargs):
    """Read in file, return dataframe"""
    filename = kwargs.get("filename")
    with open(filename, "rt", encoding="utf-8", errors="ignore") as f:
        original_log = f.readlines()
        lines_we_keep = list(log_parse(original_log))
        columns_read = ["User", "Action", "Number", "Date"]
        df = pd.DataFrame(lines_we_keep, columns=columns_read)
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index(df["Date"])
    return df


def graph(events, df_sub_ref):
    color_labels = events.Number.unique()
    rgb_values = sns.color_palette("bright", len(color_labels))
    color_map = dict(zip(color_labels, rgb_values))
    labels = events["User"]
    fig, ax = plt.subplots(figsize=(16, 10))
    fig.autofmt_xdate()
    fig.tight_layout()
    ax.tick_params(axis="both", which="major", labelsize=6)
    ax.tick_params(axis="both", which="minor", labelsize=6)
    ax.xaxis_date()
    patches = [
        plt.plot(
            [],
            [],
            marker="o",
            ms=10,
            ls="",
            mec=None,
            color=rgb_values[i],
            label="{:s}".format(color_labels[i]),
        )[0]
        for i in range(len(color_labels))
    ]
    ax.legend(handles=patches, bbox_to_anchor=(0, 1), loc="upper left")
    ax.hlines(
        labels,
        date2num(events.LicOut),
        date2num(events.LicIn),
        linewidth=10,
        color=events.Number.map(color_map),
        alpha=0.8,
    )
    ax.plot(date2num(df_sub_ref.Date), df_sub_ref.User, "rx")
    plt.savefig('stardrop-date.png')
    plt.close(fig)


@functools.lru_cache(maxsize=128, typed=False)
def simple_user(uid):
    """ Take a user logon id and return their name """
    test1 = ad.AD()
    try:
        identity = test1.fetch(f"(sAMAccountName={uid})", "displayName")
    except IndexError:
        # User Not Found, return the original uid
        return uid
    identity = json.loads(identity)
    identity = identity["attributes"]["displayName"][0]
    return identity


def cmd_args(args=None):
    """Prepare commandline arguments return Namespace object of options set"""
    parser = argparse.ArgumentParser("Prepares license log for datamining.")

    parser.add_argument("filename", help="path/filename of logfile to file to parse")
    parser.add_argument(
        "-s",
        "--start",
        dest="start",
        help="Start date YYYY-MM-DDTHH:MM e.g 2020-03-23T13:24",
    )
    parser.add_argument("-e", "--end", dest="end", help="End   date YYYY-MM-DDTHH:MM")
    parser.add_argument(
        "-d",
        "--dur",
        dest="dur",
        help="Duration: Hours, Days, Weeks,  e.g. 2W for 2 weeks",
    )
    parser.add_argument(
        "-a",
        "--Active-Directory",
        dest="active_directory",
        action="store_true",
        help="Resolve user ID to real name  in Active Directory",
    )

    opt = parser.parse_args(args)
    return opt


def process_opts(opt):
    """Process cmdline options logic
    Calculate ROI start and end times from combinations supplied"""
    kwargs = {}
    kwargs = {"filename": opt.filename, **kwargs}

    if opt.dur:
        # If set get timedelta it represents
        duration = parse_duration(opt.dur)
        print(f"Duration {opt.dur}")

    if opt.dur and opt.start and opt.end:
        # Assume start and range ignore end
        opt.end_dt = date_to_dt(opt.start, DT_FORMAT) + duration
        opt.end = opt.end_dt.strftime(DT_FORMAT)

    if opt.dur and opt.start and not opt.end:
        # Start and range
        opt.end_dt = date_to_dt(opt.start, DT_FORMAT) + duration
        opt.end = opt.end_dt.strftime(DT_FORMAT)

    if opt.dur and not opt.start and opt.end:
        # Range before enddate
        opt.start_dt = date_to_dt(opt.end, DT_FORMAT) - duration
        opt.start = opt.start_dt.strftime(DT_FORMAT)

        # This won't return the full duration until we know the end date in our log
    if opt.dur and not opt.start and not opt.end:
        # End of log back by duration
        opt.end_dt = datetime.datetime.now()
        opt.end = dt_to_date(opt.end_dt, DT_FORMAT)
        opt.start_dt = date_to_dt(opt.end, DT_FORMAT) - duration
        opt.start = opt.start_dt.strftime(DT_FORMAT)

    if not opt.dur and opt.start and opt.end:
        # Date range
        if date_to_dt(opt.start, DT_FORMAT) > date_to_dt(opt.end, DT_FORMAT):
            # End before start so swap
            opt.start, opt.end = opt.end, opt.start

    if not opt.dur and opt.start and not opt.end:
        # Start Date only - from start date to end
        opt.end_dt = datetime.datetime.now()
        opt.end = opt.end_dt.strftime(DT_FORMAT)

    if not opt.dur and not opt.start and opt.end:
        # End Date only - from end date to start
        opt.start_dt = datetime.date(1970, 1, 1)
        opt.start = opt.start_dt.strftime(DT_FORMAT)

    if opt.active_directory:
        # Resolve uid to realname in Active Directory
        kwargs = {"active_directory": True, **kwargs}

    return kwargs


def parse_duration(duration):
    """Parse duration Hours,Days or Weeks Return timedelta"""
    hours = datetime.timedelta(hours=1)
    days = datetime.timedelta(days=1)
    weeks = datetime.timedelta(weeks=1)
    fields = re.split(r"(\d+)", duration)
    duration = int(fields[1])
    if fields[2][:1].upper() == "H":
        duration_td = duration * hours
    elif fields[2][:1].upper() == "D":
        duration_td = duration * days
    elif fields[2][:1].upper() == "W":
        duration_td = duration * weeks
    else:
        raise ValueError

    return duration_td


def date_to_dt(datestring, FORMAT):
    """Convert date string to datetime object"""
    dateasdt = datetime.datetime.strptime(datestring, FORMAT)
    return dateasdt


def dt_to_date(dateasdt, FORMAT):
    """Convert datetime object to datestring"""
    datestring = datetime.datetime.strftime(dateasdt, FORMAT)
    return datestring


def main(args=None):
    """Start of main function"""
    opt = cmd_args(args)
    kwargs = process_opts(opt)
    df = readfile_to_dataframe(**kwargs)
    # Select observations between two datetimes
    if opt.start:
        df_sub = df.loc[opt.start : opt.end].copy()
    else:
        df_sub = df  # or use the whole dataset

    # Enable for AD lookup of User's real name
    if kwargs.get("active_directory"):
        df_sub["User"] = df_sub.apply(lambda row: simple_user(row.User), axis=1)

    # Unique users in time range
    print(f"==Number of users: {df_sub.User.nunique()} ==")
    print("==Unique Users==")
    print(df_sub.User.unique())

    # Split Checkout and checkin events: record refusals too
    df_sub_out = df_sub[df_sub["Action"] == "License_granted"]
    df_sub_in = df_sub[
        (df_sub["Action"] == "License_released")
        | (df_sub["Action"] == "Purging_license")
    ]
    df_sub_ref = df_sub[df_sub["Action"] == "License_refused"]
    # Cumulative license loan tally
    # not needed here yet

    # Events table: For every checkout get checkin; calculate the loan duration
    events = pd.DataFrame(columns=["LicOut", "LicIn", "Number", "Duration", "User"])
    for row in df_sub_out.itertuples():
        index = getattr(row, "Index")
        user = getattr(row, "User")
        out_time = getattr(row, "Date")
        number = getattr(row, "Number")
        try:
            key = (
            (df_sub_in.User == user)
            & (df_sub_in.index >= index)
            &(df_sub_in.Number == number)
            )
            result = df_sub_in.loc[key]
            events.loc[len(events), :] = (
                out_time,
                (result.Date.iloc[0]),
                number,
                (result.Date.iloc[0] - out_time),
                user,
            )
        except IndexError:
            print(f"No MATCH! {row}")
        else:
            pass

    events["LicOut"] = pd.to_datetime(events["LicOut"], utc=True)
    events["LicIn"] = pd.to_datetime(events["LicIn"], utc=True)
    events["Duration"] = pd.to_timedelta(events["Duration"])
    # print(df_sub_ref.query('User == "Bloggs Fred SITE" or User == "Blow Joe SITE"' ))
    # Assign names to license features
    events["Number"].replace({"514": "wibble", "520": "munge", "544": "pharg", "546": "mulch"}, inplace=True)
    graph(events, df_sub_ref)


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except ValueError as e:
        print(f"Give me something to do: {e}")
        sys.exit(1)
