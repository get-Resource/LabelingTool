from django.shortcuts import render
from django.http import Http404, HttpResponse
from ua_parser import user_agent_parser
import ast

from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from segmentation.models import Image, LabelName, Segment
from django.conf import settings
from django.views.decorators.clickjacking import xframe_options_exempt

MIN_VERTICES = 3

@ensure_csrf_cookie
def index(request):
    context = {}
    context['label_image'] = Image.objects.filter(annotated=False)[0].id
    context['review_image'] = Image.objects.filter(reviewed=False)[0].id
    return render(request, 'index.html', context)

@ensure_csrf_cookie
def question(request,image_id):
    context = {}
    next_image_id = Image.objects.filter(annotated=False)[0].id
    context['next_image_id'] = str(next_image_id)
    return render(request,'question.html', context)

@ensure_csrf_cookie
def question_review(request,image_id):
    context = {}
    not_reviewed = Image.objects.filter(reviewed=False)
    valid_ids = [x.id for x in not_reviewed if x != image_id]
    context['next_image_id'] = str(valid_ids[0])
    return render(request,'question_review.html', context)

@ensure_csrf_cookie
def segment(request, image_id):
    if request.method == 'POST':
        results = ast.literal_eval(request.POST['results'])
        labels = ast.literal_eval(request.POST['labs'])
        image = Image.objects.get(id=image_id)
        Segment.objects.filter(image=image).delete()
        save_segments(image_id, results, labels)
        return json_success_response()
    else:
    	response = browser_check(request)
    	image = Image.objects.get(id=image_id)
        segments = image.segment_set.all()
        labels = [str(s.label.name) for s in segments]
        coords = []
        for s in segments:
            values = [float(x) for x in s.coords.split(',')]
            c = []
            for i in range(0, len(values),2):
                temp = {'x': values[i], 'y': values[i+1]}
                c.append(temp)
            coords.append(c)

    	context = {}
    	context['content'] = {'id': image_id, 'url': image.image.url}
     	context['min_vertices'] = MIN_VERTICES
    	context['instructions'] = 'segment/segment_inst_content.html'
        context['label_html'] = create_label_html()
        context['coords'] = coords
        context['labels'] = labels

    	response = render(request, 'segment/segment.html', context)
    	response['x-frame-options'] = 'EXEMPT'
    	return response

@ensure_csrf_cookie
def review(request, image_id):
    if request.method == 'POST':
        print request.POST['labs']
        accepted = str(request.POST['accepted'])
        if accepted == "false":
            accepted = False
        else:
            accepted = True
        results = ast.literal_eval(request.POST['results'])
        labels = ast.literal_eval(request.POST['labs'])

        imObj = Image.objects.get(id=image_id)
        if accepted:
            imObj.reviewed = True
            imObj.save()
            Segment.objects.filter(image=imObj).delete()
            save_segments(image_id, results, labels, reviewing=True)
        else:
            imObj.annotated = False
            imObj.save()
        return json_success_response()
    else:
        response = browser_check(request)
        image = Image.objects.get(id=image_id)
        segments = image.segment_set.all()
        labels = [str(s.label.name) for s in segments]
        coords = []
        for s in segments:
            values = [float(x) for x in s.coords.split(',')]
            c = []
            for i in range(0, len(values),2):
                temp = {'x': values[i], 'y': values[i+1]}
                c.append(temp)
            coords.append(c)

        context = {}
        context['content'] = {'id': image_id, 'url': image.image.url}
        context['instructions'] = 'review/review_inst_content.html'
        context['label_html'] = create_label_html()
        context['labels'] = labels
        context['coords'] = coords

        response = render(request, 'review/review.html', context)
        response['x-frame-options'] = 'EXEMPT'
        return response

#########
#
#  General Helper Functions
#
#########

# used to create selector for annotation labeling modal
def create_label_html():
    labels = sorted([str(l.name) for l in LabelName.objects.all()])
    label_body = '<select id="label_list">'
    for l in labels:
        label_body += '<option value="%s">%s</option>' %(l,l)
    label_body += '</select>'
    return label_body

def save_segments(image_id, points, labels, reviewing=False):
    pointList = points[str(image_id)]
    labelList = labels[str(image_id)]
    image = Image.objects.get(id=image_id)

    if len(pointList) > 0 or len(labelList) > 0:
        if reviewing:
            image.reviewed = True
        else:
            image.annotated = True
        image.save()

    for i in range(len(pointList)):
        vertexStr = ','.join([str(x) for x in pointList[i]])
        label = LabelName.objects.get(name=labelList[i])

        segment = Segment(image=image, label=label, coords=vertexStr)
        segment.save()

def html_error_response(request, error):
    return render(request, "error.html", {'message': error})

def json_success_response():
    return HttpResponse(
        '{"message": "success", "result": "success" }',
        content_type='application/json')

def browser_check(request):
    """ Only allow firefox and chrome, and no mobile """
    valid_browser = False
    if 'HTTP_USER_AGENT' in request.META:
        ua = user_agent_parser.Parse(request.META['HTTP_USER_AGENT'])
        if ua['user_agent']['family'].lower() in ('firefox', 'chrome'):
            device = ua['device']
            if 'is_mobile' not in device or not device['is_mobile']:
                valid_browser = True
    if not valid_browser:
        return html_error_response(
            request, '''
            This task requires Google Chrome. <br/><br/>
            <a class="btn" href="http://www.google.com/chrome/"
            target="_blank">Get Google Chrome</a>
        ''')
    return None
