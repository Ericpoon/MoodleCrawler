# coding:utf-8

import requests
import pickle
from lxml import etree
import re
import os
import csv

# path
COOKIE_FOLDER_PATH = './cookie'
COOKIE_PATH = COOKIE_FOLDER_PATH + '/moodle.cookie'
COURSES_FOLDER_PATH = './coursesinfo'
COURSE_FILE_MIME = '.csv'

# course csv file name format
# code_section.csv
# course csv file content format
# (code, name, section, period, link)


FORM_DATA = {
    'username': '14252023',
    'password': 'z1z1z1z1'
}

session = requests.Session()
if not os.path.exists(COURSES_FOLDER_PATH):
    os.makedirs(COURSES_FOLDER_PATH)
if not os.path.exists(COOKIE_FOLDER_PATH):
    os.makedirs(COOKIE_FOLDER_PATH)

print 'login...'
loginurl = 'http://buelearning.hkbu.edu.hk/login/index.php'
response = session.post(loginurl, data = FORM_DATA)
cookie = session.cookies
with open(COOKIE_PATH, 'wb') as f:
    pickle.dump(cookie, f)
print '  - OK - successfully login, cookie generated\n'
print 'start to fetch course info\n'

et = etree.HTML(response.content)
courseList = et.xpath('//li[@class="clickable-with-children"]/ul')[0]
print courseList
# elements in the courseList
titles = courseList.xpath('//li[@class="clickable-with-children"]/a/@title')
print titles
links = courseList.xpath('//li[@class="clickable-with-children"]/a[@title]/@href')
shorts = courseList.xpath('//li[@class="clickable-with-children"]/a/text()') # short form of course info, useless

courses = []
for i in range(len(titles)):
    title = titles[i]
    try:
        code = re.search('([A-Z]{4}.*?) ', title).group(1)
    except AttributeError:
         continue
    name = re.search(' (.*) \(', title).group(1)
    section = re.search('\(.* (.*)\)', title).group(1)
    section = re.sub('/','-', section)
    period = re.search('\[(.*)\]', title).group(1)
    if period == '2015 S2': # filter, added on 11, Jan
        info = (code, name, section, period, links[i])
        courses.append(info)

if not os.path.exists(COURSES_FOLDER_PATH):
    os.makedirs(COURSES_FOLDER_PATH)

for course in courses:
    filepath = '%s/%s_%s%s' % (COURSES_FOLDER_PATH, course[0], course[2], COURSE_FILE_MIME)
    with open(filepath, 'wb') as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(course)
        print 'course info saved: %s section %s' % (course[0], course[2])

print '\n  - OK - all course info generated\n'
print 'Program finished with %d course info generated, use downloader.' % len(courses)



# args to accept:
# stdID
# password
# filter args: course code
# filter args: period
# filter args: section
# flag:
#   handle all error only
#   download all files(default)