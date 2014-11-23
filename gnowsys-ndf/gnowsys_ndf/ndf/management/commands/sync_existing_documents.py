''' imports from installed packages '''
from django.core.management.base import BaseCommand, CommandError

from django_mongokit import get_database

try:
  from bson import ObjectId
except ImportError:  # old pymongo
  from pymongo.objectid import ObjectId

''' imports from application folders/files '''
from gnowsys_ndf.ndf.models import Node

###################################################################################################################################################################################

class Command(BaseCommand):

  help = " This script will add the new field(s) into already existing documents (only if they doesn't exists) in your database."

  def handle(self, *args, **options):
    collection = get_database()[Node.collection_name]
    # Keep latest fields to be added at top

    # Update object_value of GAttribute(s) of "Assignee" AttributeType
    # Find those whose data-type is not list/Array
    # Replace those as list of value(s)
    assignee_at = collection.Node.one(
        {'_type': "AttributeType", 'name': "Assignee"}
    )

    if assignee_at:
        res = 0
        assignee_cur = collection.Triple.find(
            {'_type': "GAttribute", 'attribute_type.$id': assignee_at._id, '$where': "Array.isArray(this.object_value) != true"}
        )

        for each in assignee_cur:
            upres = collection.update(
                        {'_id': each._id}, 
                        {'$set': {'object_value': [each.object_value]}}, 
                        upsert=False, multi=False
                    )

            res += upres['n']

        print "\n Updated following no. of Assignee GAttribute document(s): ", res

    # Updates already created has_profile_pic grelations' status - Except latest one (PUBLISHED) others' are set to DELETED
    has_profile_pic = collection.Node.one({'_type': "RelationType", 'name': u"has_profile_pic"})
    op = collection.aggregate([
        {'$match': {
        '_type': "GRelation",
        'relation_type.$id': has_profile_pic._id
        }},
        {'$group': {
        '_id': {'auth_id': "$subject"},
        'pp_data': {'$addToSet': {'gr_id': "$_id", 'status': "$status"}}
        }}
    ])

    res = 0
    for each in op["result"]:
        auth_id = each["_id"]["auth_id"]
        pub_id = None
        pub_res = 0
        del_id = []
        del_res = 0

        for l in each["pp_data"]:
            if l["status"] == u"PUBLISHED":
                pub_id = l["gr_id"]

            else:
                del_id.append(l["gr_id"])

        if not pub_id:
            pub_id = each["pp_data"][len(each["pp_data"])-1]["gr_id"]
            pub_res = collection.update({'_id': pub_id}, {'$set': {'status': u"PUBLISHED"}}, upsert=False, multi=False)
            pub_res = pub_res['n']            
            del_id.pop()

        del_res = collection.update({'_id': {'$in': del_id}}, {'$set': {'status': u"DELETED"}}, upsert=False, multi=True)

        if pub_res or del_res['n']:
            res += 1

    print "\n Updated following no. of has_profile_pic GRelation document(s): ", res

    # Updates the value of object_cardinality to 100. So that teaches will behave as 1:M (one-to-many) relation.
    teaches = collection.Node.one({'_type': "RelationType", 'name': "teaches"})
    res = collection.update({'_id': teaches._id, 'object_cardinality': {'$ne': 100}}, 
            {'$set': {'object_cardinality': 100}}, 
            upsert=False, multi=False
        )
    if res["updatedExisting"]:
        print "\n 'teaches' RelationType updated with object_cardinality: 100. Changed document: ", res['n']
    else:
        print "\n 'teaches' RelationType: no need to update."

    # Replacing object_type of "has_course" relationship from "NUSSD Course" to "Announced Course"
    ann_course = collection.Node.one({'_type': "GSystemType", 'name': "Announced Course"})
    if ann_course:
        res = collection.update({'_type': "RelationType", 'name': "has_course"}, 
                {'$set': {'object_type': [ann_course._id]}}, 
                upsert=False, multi=False
              )
        print "\n Replaced object_type of 'has_course' relationship from 'NUSSD Course' to 'Announced Course'."

    # Adds "relation_set" field (with default value as []) to all documents belonging to GSystems.
    res = collection.update({'_type': {'$nin': ["MetaType", "GSystemType", "RelationType", "AttributeType", "GRelation", "GAttribute", "ReducedDocs", "ToReduceDocs", "IndexedWordList", "node_holder"]}, 'relation_set': {'$exists': False}}, 
                            {'$set': {'relation_set': []}}, 
                            upsert=False, multi=True
    )
    print "\n 'relation_set' field added to following no. of documents: ", res['n']

    # Adds "attribute_set" field (with default value as []) to all documents belonging to GSystems.
    res = collection.update({'_type': {'$nin': ["MetaType", "GSystemType", "RelationType", "AttributeType", "GRelation", "GAttribute", "ReducedDocs", "ToReduceDocs", "IndexedWordList", "node_holder"]}, 'attribute_set': {'$exists': False}}, 
                            {'$set': {'attribute_set': []}}, 
                            upsert=False, multi=True
    )
    print "\n 'attribute_set' field added to following no. of documents: ", res['n']

    # Adds "license" field (with default value as "") to all documents belonging to GSystems (except Author).
    res = collection.update({'_type': {'$nin': ["MetaType", "Author", "GSystemType", "RelationType", "AttributeType", "GRelation", "GAttribute", "ReducedDocs", "ToReduceDocs", "IndexedWordList", "node_holder"]}, 'license': {'$exists': False}}, 
                            {'$set': {'license': ""}}, 
                            upsert=False, multi=True
    )
    print "\n 'license' field added to following no. of documents: ", res['n']

    # Adding "Agency_type" field adding to group documents with default values
    res = collection.update({'_type': {'$in': ['Group']}, 'agency_type': {'$exists': False}}, 
                            {'$set': {'agency_type': "Project" }}, 
                            upsert=False, multi=True
    )
    if res['n']:
           print "\n 'agency_type' field added to 'Group' documents totalling to : ", res['n']

    # Adding "Agency_type" field adding to author documents with default values
    res = collection.update({'_type': {'$in': ['Author']}, 'agency_type': {'$exists': False}}, 
                            {'$set': {'agency_type': "Others" }}, 
                            upsert=False, multi=True
    )
    if res['n']:
           print "\n 'agency_type' field added to 'Author' documents totalling to : ", res['n']


    # Modify language field with unicode value if any document has language with dict datatype
    res = collection.update({'language': {}},
                            {'$set': {'language': u""}}, 
                            upsert=False, multi=True
    )

    # Removing existing "cr_or_xcr" field with no default value
    res = collection.update({'_type': {'$in': ['Group']}, 'cr_or_xcr': {'$exists': True}}, 
                            {'$unset': {'cr_or_xcr': False }}, 
                            upsert=False, multi=True
    )
    if res['n']:
           print "\n Already existing 'cr_or_xcr' field removed from documents totalling to : ", res['n']

    # Adding "curricular" field with no default value
    res = collection.update({'_type': {'$in': ['Group']}, 'curricular': {'$exists': False}}, 
                            {'$set': {'curricular': False }}, 
                            upsert=False, multi=True
    )
    print "\n 'curricular' field added to all Group documents totalling to : ", res['n']

    # Removing existing "partners" field with no default value
    res = collection.update({'_type': {'$in': ['Group']}, 'partners': {'$exists': True}}, 
                            {'$unset': {'partners': False }}, 
                            upsert=False, multi=True
    )
    if res['n']:
           print "\n Already existing 'partners' field removed from documents totalling to : ", res['n']

    # Adding "partner" field with no default value
    res = collection.update({'_type': {'$in': ['Group']}, 'partner': {'$exists': False}}, 
                            {'$set': {'partner': False }}, 
                            upsert=False, multi=True
    )
    print "\n 'partner' field added to all Group documents totalling to : ", res['n']



    # Adding "preferred_languages" field with no default value
    res = collection.update({'_type': {'$in': ['Author']}, 'preferred_languages': {'$exists': False}}, 
                            {'$set': {'preferred_languages': {}}}, 
                            upsert=False, multi=True
    )
    print "\n 'preferred_languages' field added to all author documents totalling to : ", res['n']
    


    # Adding "rating" field with no default value
    res = collection.update({'_type': {'$nin': ['GAttribute', 'GRelation', "ReducedDocs", "ToReduceDocs", "IndexedWordList", "node_holder"]}, 'rating': {'$exists': False}}, 
                            {'$set': {'rating': []}}, 
                            upsert=False, multi=True
    )
    print "\n 'rating' field added to following no. of documents: ", res['n']
    
    # Adds 'subject_scope', 'attribute_type_scope', 'object_value_scope' field (with default value as "") to all documents which belongs to GAttribute
    res = collection.update({'_type': {'$in': ["Group", "Author"]}, 'group_admin': {'$exists': False}}, 
                            {'$set': {'group_admin': []}}, 
                            upsert=False, multi=True
    )
    print "\n 'group_admin' field added to following no. of documents: ", res['n']

    # Adds 'subject_scope', 'attribute_type_scope', 'object_value_scope' field (with default value as "") to all documents which belongs to GAttribute
    res = collection.update({'_type': "GAttribute", 'subject_scope': {'$exists': False}, 'attribute_type_scope': {'$exists': False}, 'object_value_scope': {'$exists': False}}, 
                            {'$set': {'subject_scope':"", 'attribute_type_scope':"", 'object_value_scope': ""}}, 
                            upsert=False, multi=True
    )
    print "\n 'subject_scope', 'attribute_type_scope', 'object_value_scope' fields added to following no. of documents: ", res['n']

    # Adds 'subject_scope', 'relation_type_scope', 'right_subject_scope' field (with default value as "") to all documents which belongs to GRelation
    res = collection.update({'_type': "GRelation", 'subject_scope': {'$exists': False}, 'relation_type_scope': {'$exists': False}, 'right_subject_scope': {'$exists': False}}, 
                            {'$set': {'subject_scope':"", 'relation_type_scope':"", 'right_subject_scope': ""}}, 
                            upsert=False, multi=True
    )
    print "\n 'subject_scope', 'relation_type_scope', 'right_subject_scope' fields added to following no. of documents: ", res['n']

    # Adds "annotations" field (with default value as []) to all documents belonging to GSystems
    res = collection.update({'_type': {'$nin': ["MetaType", "GSystemType", "RelationType", "AttributeType", "GRelation", "GAttribute", "ReducedDocs", "ToReduceDocs", "IndexedWordList", "node_holder"]}, 'annotations': {'$exists': False}}, 
                            {'$set': {'annotations': []}}, 
                            upsert=False, multi=True
    )
    print "\n annotations field added to following no. of documents: ", res['n']

    # Adds "group_set" field (with default value as []) to all documents except those which belongs to either GAttribute or GRelation
    res = collection.update({'_type': {'$nin': ["GAttribute", "GRelation", "ReducedDocs", "ToReduceDocs", "IndexedWordList", "node_holder"]}, 'group_set': {'$exists': False}}, 
                            {'$set': {'group_set': []}}, 
                            upsert=False, multi=True
    )
    print "\n group_set field added to following no. of documents: ", res['n']

    # Adds "property_order" field (with default value as []) to all documents except those which belongs to either GAttribute or GRelation
    res = collection.update({'_type': {'$nin': ["GAttribute", "GRelation", "ReducedDocs", "ToReduceDocs", "IndexedWordList", "node_holder"]}, 'property_order': {'$exists': False}}, 
                            {'$set': {'property_order': []}}, 
                            upsert=False, multi=True
    )
    print "\n property_order field added to following no. of documents: ", res['n']

    # Adding "modified_by" field with None as it's default value
    res = collection.update({'_type': {'$nin': ['GAttribute', 'GRelation', "ReducedDocs", "ToReduceDocs", "IndexedWordList", "node_holder"]}, 'modified_by': {'$exists': False}}, 
                            {'$set': {'modified_by': None}}, 
                            upsert=False, multi=True
    )
    print "\n modified_by field added to following no. of documents: ", res['n']

    # Adding "complex_data_type" field with empty list as it's default value
    res = collection.update({'_type': 'AttributeType', 'complex_data_type': {'$exists': False}}, 
                            {'$set': {'complex_data_type': []}}, 
                            upsert=False, multi=True
    )
    print "\n complex_data_type field added to following no. of documents: ", res['n']

    # Adding "post_node" field with empty list as it's default value
    res = collection.update({'_type': {'$nin': ['GAttribute', 'GRelation', "ReducedDocs", "ToReduceDocs", "IndexedWordList", "node_holder"]}, 'post_node': {'$exists': False}}, 
                            {'$set': {'post_node': []}}, 
                            upsert=False, multi=True
    )
    print "\n post_node field added to following no. of documents: ", res['n']

    # Adding "collection_set" field with empty list as it's default value
    res = collection.update({'_type': {'$nin': ['GAttribute', 'GRelation', "ReducedDocs", "ToReduceDocs", "IndexedWordList", "node_holder"]}, 'collection_set': {'$exists': False}}, 
                            {'$set': {'collection_set': []}}, 
                            upsert=False, multi=True
    )
    print "\n collection_set field added to following no. of documents: ", res['n']

    # Adding "location" field with no default value
    res = collection.update({'_type': {'$nin': ['GAttribute', 'GRelation', "ReducedDocs", "ToReduceDocs", "IndexedWordList", "node_holder"]}, 'location': {'$exists': False}}, 
                            {'$set': {'location': []}}, 
                            upsert=False, multi=True
    )
    print "\n location field added to following no. of documents: ", res['n'], "\n"

    # Adding "language" field with no default value
    res = collection.update({'_type': {'$nin': ['GAttribute', 'GRelation', "ReducedDocs", "ToReduceDocs", "IndexedWordList", "node_holder"]}, 'language': {'$exists': False}}, 
                            {'$set': {'language': unicode('')}}, 
                            upsert=False, multi=True
    )
    
    # Adding "access_policy" field
    # For Group documents, access_policy value is set depending upon their 
    # group_type values, i.e. either PRIVATE/PUBLIC whichever is there
    collection.update({'_type': 'Group', 'group_type': 'PRIVATE'}, {'$set': {'access_policy': u"PRIVATE"}}, upsert=False, multi=True)
    collection.update({'_type': 'Group', 'group_type': 'PUBLIC'}, {'$set': {'access_policy': u"PUBLIC"}}, upsert=False, multi=True)
    
    # For Non-Group documents which doesn't consits of access_policy field, add it with PUBLIC as it's default value
    collection.update({'_type': {'$nin': ['Group', 'GAttribute', 'GRelation', "ReducedDocs", "ToReduceDocs", "IndexedWordList", "node_holder"]}, 'access_policy': {'$exists': False}}, {'$set': {'access_policy': u"PUBLIC"}}, upsert=False, multi=True)
    
    collection.update({'_type': {'$nin': ['Group', 'GAttribute', 'GRelation', "ReducedDocs", "ToReduceDocs", "IndexedWordList", "node_holder"]}, 'access_policy': {'$in': [None, "PUBLIC"]}}, {'$set': {'access_policy': u"PUBLIC"}}, upsert=False, multi=True)
    collection.update({'_type': {'$nin': ['Group', 'GAttribute', 'GRelation', "ReducedDocs", "ToReduceDocs", "IndexedWordList", "node_holder"]}, 'access_policy': "PRIVATE"}, {'$set': {'access_policy': u"PRIVATE"}}, upsert=False, multi=True)

    
