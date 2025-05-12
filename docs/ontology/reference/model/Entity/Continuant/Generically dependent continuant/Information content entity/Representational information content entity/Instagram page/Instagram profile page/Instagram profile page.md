# Instagram profile page

## Overview

### Definition
An instagram profile page at a specific point in time, consisting of a unique identifier, visual representation, and metadata about the profile's content and social connections

### Examples
- A snapshot of John's Instagram profile as viewed on 2023-11-10

### Aliases
Not defined.

### URI
http://ontology.naas.ai/abi/InstagramProfilePage

### Subclass Of
- Instagram Page: http://ontology.naas.ai/abi/InstagramPage

### Ontology Reference
Not defined.

### Hierarchy
```mermaid
graph BT
    InstagramProfilePage(Instagram<br>profile<br>page):::ABI-->InstagramPage
    InstagramPage(Instagram<br>page):::ABI-->ont00001069
    ont00001069(Representational<br>information<br>content<br>entity):::ABI-->ont00000958
    ont00000958(Information<br>content<br>entity):::BFO-->BFO_0000031
    BFO_0000031(Generically<br>dependent<br>continuant):::BFO-->BFO_0000002
    BFO_0000002(Continuant):::BFO-->BFO_0000001
    BFO_0000001(Entity):::BFO
    
    classDef BFO fill:#97c1fb,color:#060606
    classDef CCO fill:#e4c51e,color:#060606
    classDef ABI fill:#48DD82,color:#060606
```

## Properties
### Data Properties
| Label | Definition | Example | Domain | Range |
|-------|------------|---------|--------|-------|
| [biography](http://ontology.naas.ai/abi/profile_picture_url) | A string that is a text description of the Instagram profile owner and is part of the profile's essential identity | Don't be dead serious about your life, it's just a play. | [Instagram Profile Page](http://ontology.naas.ai/abi/InstagramProfilePage) | ['http://www.w3.org/2001/XMLSchema#string'] |
| [display name](http://ontology.naas.ai/abi/profile_picture_url) | A string that is the public name shown on the Instagram profile and is part of the profile's essential identity | Jeremy Lvr | [Instagram Profile Page](http://ontology.naas.ai/abi/InstagramProfilePage) | ['http://www.w3.org/2001/XMLSchema#string'] |
| [follower count](http://ontology.naas.ai/abi/profile_picture_url) | An integer that is the number of accounts following this Instagram profile and is part of the profile's essential identity | 204 | [Instagram Profile Page](http://ontology.naas.ai/abi/InstagramProfilePage) | ['http://www.w3.org/2001/XMLSchema#integer'] |
| [following count](http://ontology.naas.ai/abi/profile_picture_url) | An integer that is the number of accounts this Instagram profile follows and is part of the profile's essential identity | 410 | [Instagram Profile Page](http://ontology.naas.ai/abi/InstagramProfilePage) | ['http://www.w3.org/2001/XMLSchema#integer'] |
| [is private](http://ontology.naas.ai/abi/profile_picture_url) | A boolean that indicates whether the Instagram account is private and is part of the profile's essential identity | false | [Instagram Profile Page](http://ontology.naas.ai/abi/InstagramProfilePage) | ['http://www.w3.org/2001/XMLSchema#boolean'] |
| [is verified](http://ontology.naas.ai/abi/profile_picture_url) | A boolean that indicates whether the Instagram account has been verified by Instagram as authentic and is part of the profile's essential identity | false | [Instagram Profile Page](http://ontology.naas.ai/abi/InstagramProfilePage) | ['http://www.w3.org/2001/XMLSchema#boolean'] |
| [platform name](http://ontology.naas.ai/abi/profile_picture_url) | A string that is the name of the social media platform where the profile exists and is part of the profile's essential identity | Instagram | [Instagram Profile Page](http://ontology.naas.ai/abi/InstagramProfilePage) | ['http://www.w3.org/2001/XMLSchema#string'] |
| [post count](http://ontology.naas.ai/abi/profile_picture_url) | An integer that is the number of posts published by the Instagram profile and is part of the profile's essential identity | 46 | [Instagram Profile Page](http://ontology.naas.ai/abi/InstagramProfilePage) | ['http://www.w3.org/2001/XMLSchema#integer'] |
| [profile id](http://ontology.naas.ai/abi/profile_picture_url) | A string that is the unique identifier for an Instagram profile and is part of the profile's essential identity | jeremy_lvr | [Instagram Profile Page](http://ontology.naas.ai/abi/InstagramProfilePage) | ['http://www.w3.org/2001/XMLSchema#string'] |
| [profile picture URL](http://ontology.naas.ai/abi/profile_picture_url) | A URI that is the URL of the profile picture image and is part of the profile's essential identity | https://www.instagram.com/jeremy_lvr/profile_pic/ | [Instagram Profile Page](http://ontology.naas.ai/abi/InstagramProfilePage) | ['http://www.w3.org/2001/XMLSchema#anyURI'] |

### Object Properties
| Label | Definition | Example | Domain | Range | Inverse Of |
|-------|------------|---------|--------|-------|------------|
| [exists at](https://www.commoncoreontologies.org/ont00001938) | (Elucidation) exists at is a relation between a particular and some temporal region at which the particular exists | First World War exists at 1914-1916; Mexico exists at January 1, 2000 | [entity](http://purl.obolibrary.org/obo/BFO_0000001) | [temporal region](http://purl.obolibrary.org/obo/BFO_0000008) | []([]) |
| [continuant part of](https://www.commoncoreontologies.org/ont00001938) | b continuant part of c =Def b and c are continuants & there is some time t such that b and c exist at t & b continuant part of c at t | Milk teeth continuant part of human; surgically removed tumour continuant part of organism | [continuant](http://purl.obolibrary.org/obo/BFO_0000002) | [continuant](http://purl.obolibrary.org/obo/BFO_0000002) | [has continuant part](http://purl.obolibrary.org/obo/BFO_0000178) |
| [has continuant part](https://www.commoncoreontologies.org/ont00001938) | b has continuant part c =Def c continuant part of b |  | [continuant](http://purl.obolibrary.org/obo/BFO_0000002) | [continuant](http://purl.obolibrary.org/obo/BFO_0000002) | []([]) |
| [is output of](https://www.commoncoreontologies.org/ont00001938) | x is_output_of y iff x is an instance of Continuant and y is an instance of Process, such that the presence of x at the end of y is a necessary condition for the completion of y. |  | [continuant](http://purl.obolibrary.org/obo/BFO_0000002) | [process](http://purl.obolibrary.org/obo/BFO_0000015) | [has output](https://www.commoncoreontologies.org/ont00001986) |
| [is input of](https://www.commoncoreontologies.org/ont00001938) | x is_input_of y iff x is an instance of Continuant and y is an instance of Process, such that the presence of x at the beginning of y is a necessary condition for the start of y. |  | [continuant](http://purl.obolibrary.org/obo/BFO_0000002) | [process](http://purl.obolibrary.org/obo/BFO_0000015) | [has input](https://www.commoncoreontologies.org/ont00001921) |
| [is affected by](https://www.commoncoreontologies.org/ont00001938) | x is_affected_by y iff x is an instance of Continuant and y is an instance of Process, and y influences x in some manner, most often by producing a change in x. |  | [continuant](http://purl.obolibrary.org/obo/BFO_0000002) | [process](http://purl.obolibrary.org/obo/BFO_0000015) | []([]) |
| [is concretized by](https://www.commoncoreontologies.org/ont00001938) | c is concretized by b =Def b concretizes c |  | [generically dependent continuant](http://purl.obolibrary.org/obo/BFO_0000031) | {'or': {'or': ['http://purl.obolibrary.org/obo/BFO_0000015']}} | [concretizes](http://purl.obolibrary.org/obo/BFO_0000059) |
| [generically depends on](https://www.commoncoreontologies.org/ont00001938) | b generically depends on c =Def b is a generically dependent continuant & c is an independent continuant that is not a spatial region & at some time t there inheres in c a specifically dependent continuant which concretizes b at t |  | [generically dependent continuant](http://purl.obolibrary.org/obo/BFO_0000031) | {'and': {'and': ['http://purl.obolibrary.org/obo/BFO_0000004']}} | [is carrier of](http://purl.obolibrary.org/obo/BFO_0000101) |
| [is about](https://www.commoncoreontologies.org/ont00001938) | A primitive relationship between an Information Content Entity and some Entity. |  | [Information Content Entity](https://www.commoncoreontologies.org/ont00000958) | [entity](http://purl.obolibrary.org/obo/BFO_0000001) | []([]) |
| [represents](https://www.commoncoreontologies.org/ont00001938) | x represents y iff x is an instance of Information Content Entity, y is an instance of Entity, and z is carrier of x, such that x is about y in virtue of there existing an isomorphism between characteristics of z and y. |  | [Representational Information Content Entity](https://www.commoncoreontologies.org/ont00001069) |  | []([]) |
| [has followers](https://www.commoncoreontologies.org/ont00001938) | An instagram profile page has followers | John's Instagram profile page has followers | [Instagram Profile Page](http://ontology.naas.ai/abi/InstagramProfilePage) | [Instagram Profile Page](http://ontology.naas.ai/abi/InstagramProfilePage) | []([]) |
| [has instagram post](https://www.commoncoreontologies.org/ont00001938) | An instagram profile page has an instagram post | John's Instagram profile page has a post about his new book | [Instagram Profile Page](http://ontology.naas.ai/abi/InstagramProfilePage) | [Instagram Post Page](http://ontology.naas.ai/abi/InstagramPostPage) | []([]) |
| [is following](https://www.commoncoreontologies.org/ont00001938) | An instagram profile page is following another instagram profile page | John's Instagram profile page is following Jane's Instagram profile page | [Instagram Profile Page](http://ontology.naas.ai/abi/InstagramProfilePage) | [Instagram Profile Page](http://ontology.naas.ai/abi/InstagramProfilePage) | []([]) |
