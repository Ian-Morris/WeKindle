#!usr/bin/Python
# -*- coding:utf-8 -*-
from flask import render_template, redirect, url_for, flash
from flask.ext.login import login_required, current_user
from . import main
from .forms import EditProfileForm, EditProfileAdminForm, SubscribeForm
from .. import db
from ..models import Role, User, OfficialAccount
from ..decorators import admin_required
from ..tasks import send_email


# parse
import requests
from urllib import urlencode, quote
import re

import sys
reload(sys)
sys.setdefaultencoding('utf-8')

@main.route('/', methods=['GET', 'POST'])
def index():
    form = SubscribeForm()
    if current_user.is_authenticated():
        subscribed_accounts = current_user.subscribed_accounts.all()
        if form.validate_on_submit():
            account_name = form.official_account_name.data
            account_id = form.official_account_id.data
            account = OfficialAccount.query.filter_by(name=account_id).first()
            # new account
            if account is None:
                openid, account_des = get_official_account_info(account_name.encode('gb2312'),
                                                                account_id)
                account = OfficialAccount(id=openid,
                                          name=account_id,
                                          title=account_name,
                                          description=account_des)
                db.session.add(account)
                
            # is subscribed by current user or not
            if account in subscribed_accounts:
                flash('You have already subscribed the account.')
            else:
                current_user.subscribed_accounts.append(account)
                db.session.add(current_user)
            return redirect(url_for('.index'))
        return render_template('index.html', form=form, subscriptions=subscribed_accounts)
    return render_template('index.html', form=form, subscriptions=None)

@main.route('/delete-official-account/<path:id>')
@login_required
def delete_official_account(id):
    account = OfficialAccount.query.filter_by(id=id).first()
    if account is not None:
        current_user.subscribed_accounts.remove(account)
    else:
        flash('The account does not exist!')
    return redirect(url_for('.index'))


@main.route('/deliver/<path:id>')
@login_required
def deliver(id):
    # several accounts, one book
    # celery
    send_email(current_user.email, 'New User', 'mail/new_user', user=current_user)
    return redirect(url_for('.index'))

@main.route('/user/<username>')
def user(username):
    user = User.query.filter_by(username=username).first_or_404()
    return render_template('user.html', user=user)


@main.route('/edit-profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm()
    if form.validate_on_submit():
        current_user.name = form.name.data
        current_user.location = form.location.data
        current_user.about_me = form.about_me.data
        db.session.add(current_user)
        flash('Your profile has been updated.')
        return redirect(url_for('.user', username=current_user.username))
    form.name.data = current_user.name
    form.location.data = current_user.location
    form.about_me.data = current_user.about_me
    return render_template('edit_profile.html', form=form)


@main.route('/edit-profile/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_profile_admin(id):
    user = User.query.get_or_404(id)
    form = EditProfileAdminForm(user=user)
    if form.validate_on_submit():
        user.email = form.email.data
        user.username = form.username.data
        user.confirmed = form.confirmed.data
        user.role = Role.query.get(form.role.data)
        user.name = form.name.data
        user.location = form.location.data
        user.about_me = form.about_me.data
        db.session.add(user)
        flash('The profile has been updated.')
        return redirect(url_for('.user', username=user.username))
    form.email.data = user.email
    form.username.data = user.username
    form.confirmed.data = user.confirmed
    form.role.data = user.role_id
    form.name.data = user.name
    form.location.data = user.location
    form.about_me.data = user.about_me
    return render_template('edit_profile.html', form=form, user=user)



# parse official accounts
rgx_openid = re.compile(r'href="\/gzh\?openid=(.*?)"')
rgx_official_account_name = re.compile(r'<!--red_beg-->(.*?)<!--red_end-->')
rgx_official_account_id = re.compile(ur'>微信号：(.*?)<')
rgx_resnum = re.compile(r'<resnum id="scd_num">(.*?)<\/resnum>')
rgx_official_account_des = re.compile(ur'功能介绍：<\/span><.*?>(.*?)<\/span>')

def get_official_account_info(official_account_name, id):
    headers = {
         'User-Agent':"Mozilla/5.0 (compatible; MSIE 9.0; Windows NT 6.1; Win64; x64; Trident/5.0)",
         'Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            }
    openid = None
    escaped_name = quote(official_account_name)
    page = 1
    total_page = None
    account_des =""
    while openid is None: 
        search_url = 'http://weixin.sogou.com/weixin?query=' + escaped_name + '&page='+ repr(page)
        r = requests.post(search_url, headers)
        print r.status_code
        if r.status_code != 200:
            continue
        print r.encoding
        content = r.text
        if total_page is None:
            match_resnum = rgx_resnum.search(content)
            if match_resnum:
                total_items = int(match_resnum.group(1))
                total_page = total_items/10
                if total_items%10 != 0:
                    total_page += 1
        for match_openid in rgx_openid.finditer(content):
            match_name = rgx_official_account_name.search(content, match_openid.start())
            match_id = rgx_official_account_id.search(content, match_name.start())
            if match_id:
                if match_id.group(1) == id:
                    openid = match_openid.group(1)
                    match_des = rgx_official_account_des.search(content, match_id.start())
                    if match_des:
                        account_des = match_des.group(1).replace("<em><!--red_beg-->", "")\
                        .replace("<!--red_end--></em>", "")
                    break
        page += 1
        if page == total_page:
            break;
    return openid, account_des

