#!/usr/bin/env python3
# coding: utf-8
"""Parse Optibrium Geneious Flexlm style log file.
   Show graphics of useage and availability of license """
import re
import argparse
import sys
import json
import datetime
import functools
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.dates import date2num
import seaborn as sns

# import ADlookup as ad

# Set ISO 8601 Datetime format e.g. 2020-12-22T14:30
DT_FORMAT = "%Y-%m-%dT%H:%M"


def log_parse(original_log, **kwargs):
    """Take logfile and add date to every time.
    Keep only the events we're interested in"""
    grabbag = ["IN:", "OUT:", "DENIED:", "QUEUED:", "DEQUEUED:"]
    if kwargs.get("hint"):
        current_date = datetime.date.fromisoformat(kwargs.get("hint"))
    else:
        cr_date = "2019-01-01"  # Kludge we should only start at first TIMESTAMP unless we use a --hint
        current_date = date_to_dt(cr_date, "%Y-%m-%d")

    # set unixtime on first record (ensure sucessive records only advance and don't pass midnight with no new date)
    lasttime = dt_to_timestamp(current_date)

    for line in original_log:
        data = line.split()
        if len(data) < 4:
            continue
        if data[1] != "(geneious)":
            continue
        try:
            # Do we have a TIMESTAMP, if we do and it's newer then use it
            if data[2] == "TIMESTAMP":
                new_date = datetime.datetime.strptime(data[3], "%m/%d/%Y").date()
                # If it hasn't changed then value of current_date is OK
                if new_date == current_date:
                    pass
                else:
                    # if it has changed, then that's the new value of current_date
                    current_date = new_date
                    print(current_date)
                    continue
        except IndexError:
            continue

        if [i for i in grabbag if i in data[2]]:
            record_date = current_date.strftime("%Y-%m-%d")

            data = f"{record_date} " + " ".join(re.split(r"\s+|@|\.", line))
            data = data.split(maxsplit=6)
            # Before we deliver a record, make sure the carriage hasn't become a pumpkin
            unixtime = date_to_timestamp(f"{data[0]}T{data[1]}", "%Y-%m-%dT%H:%M:%S")
            if unixtime >= lasttime:
                pass
            else:
                print("AWOOGA!!! ALERT we have a pumpkin. Fixed rollover date")
                # add on a day here
                newdate = date_to_dt(data[0], "%Y-%m-%d") + datetime.timedelta(days=1)
                data[0] = dt_to_date(newdate, "%Y-%m-%d")
                current_date = newdate
                unixtime = date_to_timestamp(
                    f"{data[0]}T{data[1]}", "%Y-%m-%dT%H:%M:%S"
                )
            # print(data)
            lasttime = unixtime
            yield data
        else:
            continue


def readfile_to_dataframe(**kwargs):
    """Read in file, return dataframe"""
    filename = kwargs.get("filename")
    with open(filename, "rt", encoding="utf-8", errors="ignore") as f:
        original_log = f.readlines()
        lines_we_keep = list(log_parse(original_log, **kwargs))
        columns_read = ["Date", "Time", "Product", "Action", "Module", "User", "Host"]
        discard_cols = ["Time", "Product", "Module"]
        df = pd.DataFrame.from_records(lines_we_keep, columns=columns_read)
        df["Date"] = pd.to_datetime(df["Date"] + " " + df["Time"])
        df.drop(list(discard_cols), axis=1, inplace=True)
        # df = df.set_index(df['Date'])
        df = df.set_index(pd.DatetimeIndex(df["Date"]))
        # debug df.to_csv(r'geneious-raw-df.csv', encoding='utf8')
    return df


def graph(events, df_sub_ref, loans):
    """Draw graph of license use duration per user on timeline
    plot time license unavailable as red x"""
    color_labels = events.Host.unique()
    rgb_values = sns.color_palette("Paired", len(color_labels))
    color_map = dict(zip(color_labels, rgb_values))
    labels = events["User"]
    fig, axes = plt.subplots(2, 1, sharex=True, figsize=(16, 12))
    fig.autofmt_xdate()
    axes[0] = plt.subplot2grid((6, 1), (0, 0), rowspan=5)
    axes[1] = plt.subplot2grid((6, 1), (5, 0), rowspan=1, sharex=axes[0])
    color = "tab:blue"
    axes[0].grid(which="major", axis="x")
    axes[0].tick_params(axis="both", which="major", labelsize=6)
    axes[0].tick_params(axis="both", which="minor", labelsize=6)
    axes[0].set_ylabel("Users", color=color)
    axes[0].spines["right"].set_position(("axes", 1))
    axes[0].xaxis_date()
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
    axes[0].legend(handles=patches, bbox_to_anchor=(0, 1), loc="upper left")
    axes[0].hlines(
        labels,
        date2num(events.LicOut),
        date2num(events.LicIn),
        linewidth=6,
        color=events.Host.map(color_map),
    )
    axes[0].plot(date2num(df_sub_ref.Date), df_sub_ref.User, "rx")

    loan_color = "tab:green"
    axes[1].set(ylim=(0, 36))
    axes[1].set_ylabel("Licenses checked OUT")
    axes[1].set_yticks(np.arange(0, 36, step=6))
    axes[1].grid(which="major", axis="x", alpha=0.5)
    loans.plot(ax=axes[1], color=loan_color, linewidth=1, grid=True)
    fig.tight_layout()
    # plt.show()
    plt.savefig("Geneious-date.png")
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
        "-i", "--hint", dest="hint", help="Hint start date of the log YYYY-MM-DD"
    )
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

    if opt.hint:
        # Hint is for timestamping log before first timestsmp
        current_date = opt.hint
        kwargs = {"hint": current_date, **kwargs}

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


def date_to_timestamp(datestring, FORMAT):
    """Convert date string to timestamp"""
    dateasdt = date_to_dt(datestring, FORMAT)
    unixtime = dt_to_timestamp(dateasdt)
    return unixtime


def dt_to_timestamp(dateasdt):
    """Convert datetime obj to unix timestamp"""
    unixtime = datetime.datetime.timestamp(dateasdt)
    return unixtime


def main(args=None):
    """Start of main function"""
    opt = cmd_args(args)
    kwargs = process_opts(opt)
    df = readfile_to_dataframe(**kwargs)
    overrun = 12  # Hours to look forward beyond slice to find session end
    overrun = datetime.timedelta(hours=overrun)

    # Select observations between two datetimes
    if opt.start:
        # Add some time to find the end of sessions just started within our slice
        opt.endExtra = date_to_dt(opt.end, DT_FORMAT) + overrun
        opt.endExtra = dt_to_date(opt.endExtra, DT_FORMAT)
        df_sub = df.loc[opt.start : opt.endExtra].copy()
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
    df_sub_in = df_sub[df_sub["Action"] == "IN:"]

    if opt.end:
        df_sub = df_sub.loc[: opt.end].copy()
    df_sub_out = df_sub[df_sub["Action"] == "OUT:"]
    df_sub_ref = df_sub[df_sub["Action"] == "DENIED:"]

    # print(df_sub_out.tail(30))
    # print(df_sub_in.tail(20))

    # Cumulative license loan tally
    x = df_sub_out.Date.value_counts().sub(df_sub_in.Date.value_counts(), fill_value=0)
    x.iloc[0] = 0
    loans = x.cumsum()

    # Events table: For every checkout get checkin; calculate the loan duration
    events = pd.DataFrame(columns=["LicOut", "LicIn", "Duration", "User", "Host"])
    for index, row in df_sub_out.iterrows():
        user = row.User
        out_time = row.Date
        host = row.Host
        try:
            key = (df_sub_in.User == user) & (df_sub_in.index >= index)
            result = df_sub_in.loc[key]
            events.loc[len(events), :] = (
                out_time,
                (result.Date.iloc[0]),
                (result.Date.iloc[0] - out_time),
                user,
                host,
            )
        except IndexError:
            print(f"No MATCH! {row}")
        else:
            pass

    events["LicOut"] = pd.to_datetime(events["LicOut"], utc=True)
    events["LicIn"] = pd.to_datetime(events["LicIn"], utc=True)
    events["Duration"] = pd.to_timedelta(events["Duration"])
    # Optionaly output the events table for analysis
    # print(events.tail(20))
    # events.to_csv(r'geneious-events.csv', encoding='utf8')

    # Truncate Host to 4 chars making them CAPS
    events.Host = events.Host.str.slice(0, 4)
    events.Host = events.Host.str.upper()

    # Convert Ken's machines to GBJH
    events.replace(
        to_replace=r"(LOVE|BUFF|SPIK)", value="GBJH", regex=True, inplace=True
    )
    # Convert  Shimaa Sharkawy, Rana Abdelkader Salma Yassin, Hoda Kassin to GBEX
    events.replace(
        to_replace=r"(SHAR|ABDE|YASS|KASS)", value="GBEX", regex=True, inplace=True
    )
    # Convert Workspace users to EPAM
    events.replace(to_replace=r"DESK", value="EPAM", regex=True, inplace=True)

    # Sort by Site (else graph is by login time)
    events.sort_values(by=["Host"], inplace=True)

    # Find users that forget to log out
    lazy_logins = parse_duration("12H")
    users_overtime = events[events.Duration >= lazy_logins]
    print(f"==Number of occasions users session goes over {lazy_logins} Hours==")
    print(
        users_overtime[["User", "Duration"]]
        .groupby(["User"])["Duration"]
        .agg(["count"])
        .sort_values(["count"], ascending=False)
    )

    # Output CSV of top users by site
    print('==Top users checkout duration by site== output as "Geneious-siteusers.csv"')
    df_agg = (
        events[["User", "Duration", "Host"]]
        .groupby(["Host", "User"])["Duration"]
        .agg(["sum"])
        .sort_values(["sum"], ascending=False)
    )
    df_agg.columns = df_agg.columns.str.strip()
    df_agg = df_agg.sort_values(by=["Host", "sum"], ascending=False)
    pd.set_option("display.max_colwidth", None)
    df_agg.to_excel("Geneious-siteusers.xlsx", encoding="utf8")

    print("==Number of users by site==")
    print(
        events.groupby("Host")["User"]
        .nunique()
        .sort_values(ascending=False)
        .to_string()
    )

    graph(events, df_sub_ref, loans)


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except ValueError as e:
        print(f"Give me something to do. {e}")
        sys.exit(1)
