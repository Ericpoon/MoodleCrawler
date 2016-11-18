# coding:utf-8

import requests
from lxml import etree
import os
import csv
import pickle
import time, datetime
from multiprocessing.dummy import Pool as ThreadPool
import ast
import re

# path
COOKIE_FOLDER_PATH = './cookie'
COOKIE_PATH = COOKIE_FOLDER_PATH + '/moodle.cookie'
COURSES_FOLDER_PATH = './coursesinfo'
COURSE_FILE_MIME = '.csv'
# path
ERROR_MESSAGE_FOLDER_PATH = './errormsg'
ERROR_FILE_MIME = '.txt'
# path
# NOTES_FOLDER_PATH = './moodle' # old version
# notes folder path, modified on 11, Jan
NOTES_FOLDER_PATH = '/Users/Ericp/Documents/Course Notes'

# path
DOWNLOAD_RECORD_PATH = './records'


# course csv file name format
# code_section.csv
# course csv file content format
# (code, name, section, period, link)


'''
    <parameter: course_file_name> the name of the course csv file (including .cinfo)
    <return: none>

    this func is to use the generated file (by generator.py) to get a course main page url,
    then the url is pass to func 'walk'
    (course main page contains all the files and folders)
'''
def spider(course_file_name):
    # get course url
    course_file_path = '%s/%s' % (COURSES_FOLDER_PATH, course_file_name)
    with open(course_file_path, 'rb') as file:
        reader = csv.reader(file)
        course = reader.next()
    url = course[4]
    # walk through all directory and download
    walk(url, dirt='', course=course)


'''
    <parameter: url> page url, all the files shown in this page will be downloaded
    <parameter: dirt> directory, use to store the directory of super-folder(s) for each file
        - this is later passed to 'download_all_files'
    <parameter: course> course info
        - (a list whose elements are course code, name, section, period and url link)
        - this is not used within this func, but the func 'download_all_files' will use this,
        so in order to pass this list to 'dowanloadfile', I must pass it in here first
        (maybe there's better solution)
    <return: none>

    this func walks through all the sub-folders
    (actually only one sub-folder
     'cos I dont know the html pattern of sub-sub-folder and files in it)
    this func will use xpath to locate sources(files) and folders using different patterns
        - to deal with folders, this func will walk into all the folders by calling itself 'walk'
            - recursion is applied here
        - to deal with files, this func will call 'download_all_files' to download all of them
    page is fetched here while file is downloaded in 'download_file'
'''
def walk(url, dirt, course):
    temp_course = course
    print 'fetching page content...'
    failure_counter = 0
    while True:
        try:
            if failure_counter >= 3:
                raise requests.RequestException('Attempt to login but timeout occurs frequently')
            page_content = requests.get(url, cookies=cookie, timeout=5).content
            break
        except requests.exceptions.ReadTimeout:
            print '  - Timeout - connection timeout... try angin'
            failure_counter += 1
            continue
        except requests.RequestException, e:
            print '  - Error - connection error... failed to fetch this page'
            ## handle the error
            ## the page url will be included in the error message file
            path = '%s/%s%s' % (ERROR_MESSAGE_FOLDER_PATH, time.time(), ERROR_FILE_MIME)
            with open(path, 'wb') as errorfile:
                writer = csv.writer(errorfile)
                writer.writerow(['PAGE'])
                writer.writerow([url])
                writer.writerow([dirt])
                writer.writerow([course])
                writer.writerow(['Null'])
                writer.writerow([e.message]) # exception message
                writer.writerow([datetime.datetime.now()])
            return
    print '  - OK - successfully fetched\n'

    et = etree.HTML(page_content)
    sources_1 = et.xpath('//li[@id]/div[@class="content"]/ul/li[normalize-space(@class)="activity resource modtype_resource"]')
    folders_1 = et.xpath('//li[@id]/div[@class="content"]/ul/li[normalize-space(@class)="activity folder modtype_folder"]')

    sources_2 = et.xpath('//div/ul/li/ul/li/span[@class]')
    print '%d files to download... (pattern 1 matched)' % len(sources_1)
    print '%d files to download... (pattern 2 matched)' % len(sources_2)
    print '%d sub-folders to walk through... (pattern 1 matched)\n' % len(folders_1)

    ## file handler - download all of them
    if sources_1:
        download_all_files(sources_1, pattern=1, dirt=dirt, course=temp_course)
    elif sources_2:
        ### must in sub-folders
        download_all_files(sources_2, pattern=2, dirt=dirt, course=temp_course)
    ## folder handler - go into the folder to download the file
    if folders_1:
        i = 0
        while i < len(folders_1):
            superfolder = folders_1[i].xpath('../../../@aria-label')[0] # paths of folders that is outside the file
            foldername = folders_1[i].xpath('./div/div/div/div/a/span[@class="instancename"]/text()')[0]
            folderurl = folders_1[i].xpath('./div/div/div/div/a/@href')[0]
            dirt = '%s/%s' % (superfolder, foldername)
            walk(folderurl, dirt, course)
            i += 1

'''
    <parameter: sources> the file sources which contians the file urls and names
    <parameter: pattern> pattern flag, used to determine which xpath pattern is used
    <parameter: dirt> directory, use to store the directory of super-folder(s) for each file
    <parameter: course> course info
        - this is a list including course code, name, section, period and url link
    <return: none>

    this func is used to download all files in a certain page (course root page or folder page)
'''
def download_all_files(sources, pattern, dirt, course):
    i = 0
    while i < len(sources):

        if pattern is 1:
            # dirt is '' now
            superfolder = sources[i].xpath('../../../@aria-label')[0] # paths of folders that is outside the file
            dirt = superfolder
            filename = sources[i].xpath('./div/div/div/div/a/span[@class="instancename"]/text()')[0]
            fileurl = sources[i].xpath('./div/div/div/div/a/@href')[0]
        elif pattern is 2:
            # dirt is already passed in
            filename = sources[i].xpath('./a/span[@class="fp-filename"]/text()')[0]
            fileurl = sources[i].xpath('./a/@href')[0].split('?forcedownload')[0]

        print 'downloading: %s' % filename

        ## START detect file existence
        isfileexists = False
        folderpath = '%s/%s/%s' % (NOTES_FOLDER_PATH, course[0], dirt)
        if os.path.exists(folderpath):
            existed_files = os.listdir(folderpath)
            for n in existed_files:
                if n[:len(filename)] == filename:
                    isfileexists = True
                    break
            if isfileexists:
                print '  - OK - file already exists'
                i += 1
                mark = re.sub('/','-',dirt)
                recordpath = '%s/%s-%s==%s.records' % (DOWNLOAD_RECORD_PATH, course[0], mark, filename)
                # if the records folder not exist then we need to create one first
                if not os.path.exists(DOWNLOAD_RECORD_PATH):
                    os.makedirs(DOWNLOAD_RECORD_PATH)
                with open(recordpath, 'wb') as file:  # create a record file to indicate that this file has been successfully downloaded
                    print 'recorded'
                continue
        ## END

        ## start to download the file
        i += download_file(fileurl, filename, dirt, course)

'''
    <parameter: fileurl> the url of the file to download
    <parameter: filename> name of the file,
        not including mime name which is determined after the file is downloaded
    <parameter: dirt> determine the file directory
    <parameter: course> course info
    <return: an integer> 0 or 1, used as a flag to guide
        the func 'download_all_files' whether go to next file
        or try to download current file again
            - when a file is successfully downloaded, returns 1
             to point to and download next file
            - when the file already exists, returns 1,
             to point to and download next file
            - when fail to download a file (error occurs), returns 1
             to point to and download next file
            - when timeout occurs, returns 0
             to guide 'download_all_files' to retry
            - when the downloaded file is incomplete, returns 0
             to guide 'download_all_files' to retry
'''
def download_file(fileurl, filename, dirt, course):
    # TODO: 下载速度过慢的时候要抛出异常
        mark = re.sub('/','-',dirt)
        # to avoid invalid file name due to special char like ':' and '/'
        filename = re.sub(':','-',filename)
        filename = re.sub('/','-',filename)
        filename = re.sub(r'\\','-',filename)
        
        recordpath = '%s/%s-%s==%s.records' % (DOWNLOAD_RECORD_PATH, course[0], mark, filename)
        if os.path.exists(recordpath):
            return 1  # current file already downloaded, turn to next file
        try:
            response = requests.get(fileurl, cookies=cookie, timeout=5)
        except requests.exceptions.ReadTimeout:
            print '  - Timeout - connection timeout... retry now'
            # i is not incremented here in order to try again
            return 0 # retry to download this file
        except requests.RequestException, e: # including ConnectionError, ChunkedEncodingError
            print '  - Error - connection error... failed to download this file'
            ## handle the error which makes the file fail to download,
            ## the file url will be included in the error message file
            path = '%s/%s%s' % (ERROR_MESSAGE_FOLDER_PATH, time.time(), ERROR_FILE_MIME)
            with open(path, 'wb') as errorfile:
                writer = csv.writer(errorfile)
                writer.writerow(['FILE'])
                writer.writerow([fileurl])
                writer.writerow([dirt])
                writer.writerow([course])
                writer.writerow([filename])
                writer.writerow([e.message])
                writer.writerow([datetime.datetime.now()])
            return 1 # download next file, the undownloaded file will be download in a handler later


        con = response.content
        idx = response.url.rfind('.')
        con_type = response.url[idx:] # including the dot(.)
        folderpath = '%s/%s/%s' % (NOTES_FOLDER_PATH, course[0], dirt)
        if filename[-len(con_type):] == con_type:  # if the filename has already included the con_type
            filepath = '%s/%s' % (folderpath, filename)
        else:
            filepath = '%s/%s%s' % (folderpath, filename, con_type)
        if not os.path.exists(folderpath):
            os.makedirs(folderpath)
        with open(filepath, 'wb') as file:
            file.write(con)

        ## START check the completion of the file (in case the download process is interrupted)
        if os.path.getsize(filepath) != len(con):
            print '  - Error - file incomplete, download again now (%d/%d)' % (os.path.getsize(filepath), len(con))
            os.remove(filename) # delete the incomplete file
            return 0 # retry to download this file
        else:
            # if the records folder not exist then we need to create one first
            if not os.path.exists(DOWNLOAD_RECORD_PATH):
                os.makedirs(DOWNLOAD_RECORD_PATH)
            with open(recordpath, 'wb') as file:  # create a record file to indicate that this file has been successfully downloaded
                print 'recorded'
            print '  - OK - successfully download'
            return 1 # file downloaded, go to next file
        ## END


print 'initializing...'
# check cookie existence
cookie = ''
if not os.path.exists(COOKIE_PATH):
    exit('  - Error - cookies not found, generate first')
with open(COOKIE_PATH, 'rb') as f:
    try:
        cookie = pickle.load(f)
        connection_test = requests.get(url='http://buelearning.hkbu.edu.hk/', cookies=cookie)
        if connection_test.url == 'http://buelearning.hkbu.edu.hk/login/index.php':
            raise ValueError('Expired Cookie')
    except ValueError:
        exit ('  - Error - invalid cookie\n' + 'cookie file may be tampered or expired, generate again')
if not cookie:
    exit('  - Error - cookies expired, generate again')
if not os.path.exists(ERROR_MESSAGE_FOLDER_PATH):
    os.makedirs(ERROR_MESSAGE_FOLDER_PATH)

# check course files existence
courselist = []
if os.path.exists(COURSES_FOLDER_PATH):
    coursefile_dirlist = os.listdir(COURSES_FOLDER_PATH)
    for i in coursefile_dirlist:
        if i.endswith(COURSE_FILE_MIME):
            courselist.append(i)
else:
    exit('  - Error - course files not found, generate first')

print 'initialization completed\n'


t0 = time.time()
pool = ThreadPool(8)
# TODO: 每个课程一个线程, 这样并不好, 因为有些课没有课件要下载, 最好可以每个http请求一个线程
pool.map(spider, courselist)
pool.close()
pool.join()
totaltime = time.time() - t0
print 'Finished in %.2f seconds\n' % totaltime

# spider('COMP2007_1-2-10101-10201.csv') # testing #

## START retry to download
errormsglist= os.listdir(ERROR_MESSAGE_FOLDER_PATH)
print '%d error messages found\n' % (len(errormsglist))
for i in errormsglist:
    if not i.endswith(ERROR_FILE_MIME):
        continue
    path = '%s/%s' % (ERROR_MESSAGE_FOLDER_PATH, i)
    with open(path, 'rb') as errormsg:
        reader = csv.reader(errormsg)
        flag = reader.next()[0]
        url = reader.next()[0]
        dirt = reader.next()[0]
        courseinfo = ast.literal_eval(reader.next()[0])  # load in as a list or dictionary
        filename = reader.next()[0]  # filename of a PAGE is Null
        coursecode = courseinfo[0]
    if flag == 'FILE':
        print 'retry to download the file: %s/%s' % (dirt, filename)
        download_file(url, filename, dirt, courseinfo)
    elif flag == 'PAGE':
        print 'retry to fetch a page of course: %s/%s' % (coursecode, dirt)
        walk(url, dirt, courseinfo)
    os.remove(path)
## END

print '\nProgram finished with %d error unhandled.' % (len(os.listdir(ERROR_MESSAGE_FOLDER_PATH)))

# TODO: Filter 功能, 指定哪门课, 指定section, 指定学期
