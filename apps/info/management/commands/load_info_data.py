from django.core.management.base import BaseCommand
from django.db import transaction
from apps.info.models import Category, Tag, FAQ, SOP, PolicyExplanation, TrainingArticle


class Command(BaseCommand):
    help = 'Load initial info data (Categories, Tags, FAQs, SOPs, Policy Explanations, Training Articles)'

    def handle(self, *args, **options):
        self.stdout.write('Loading initial info data...')
        
        with transaction.atomic():
            # Step 1: Create Categories
            self.stdout.write('\n1. Creating Categories...')
            categories_map = {}
            
            categories_data = [
                {
                    'slug': 'route-operations',
                    'name': 'Route Operations',
                    'description': 'Information related to planning, operating and adjusting public transport routes for the ministry.',
                    'is_active': True,
                },
                {
                    'slug': 'customer-service-complaints',
                    'name': 'Customer Service & Complaints',
                    'description': 'Guidance for handling commuter feedback, complaints and service recovery in the transport ministry.',
                    'is_active': True,
                },
                {
                    'slug': 'safety-compliance',
                    'name': 'Safety & Compliance',
                    'description': 'Policies, procedures and FAQs related to passenger, driver and road safety for public transport services.',
                    'is_active': True,
                },
                {
                    'slug': 'ticketing-fares',
                    'name': 'Ticketing & Fares',
                    'description': 'Information on tickets, concessions, fare rules and payment channels for the ministry\'s transport services.',
                    'is_active': True,
                },
                {
                    'slug': 'fleet-maintenance',
                    'name': 'Fleet Maintenance',
                    'description': 'Standard operating procedures and guidance for maintaining ministry buses and support vehicles.',
                    'is_active': True,
                },
                {
                    'slug': 'digital-channels-e-ticketing',
                    'name': 'Digital Channels & E-Ticketing',
                    'description': 'Help content for the ministry\'s mobile app, web portal and electronic ticketing solutions.',
                    'is_active': True,
                },
            ]
            
            for cat_data in categories_data:
                category, created = Category.objects.get_or_create(
                    slug=cat_data['slug'],
                    defaults={
                        'name': cat_data['name'],
                        'description': cat_data['description'],
                        'is_active': cat_data['is_active'],
                    }
                )
                categories_map[cat_data['slug']] = category
                status = 'Created' if created else 'Already exists'
                self.stdout.write(f'  {status}: {category.name}')
            
            # Step 2: Create Tags
            self.stdout.write('\n2. Creating Tags...')
            tags_map = {}
            
            tags_data = [
                {'slug': 'routes', 'name': 'routes'},
                {'slug': 'fares', 'name': 'fares'},
                {'slug': 'lost-and-found', 'name': 'lost-and-found'},
                {'slug': 'complaints', 'name': 'complaints'},
                {'slug': 'safety', 'name': 'safety'},
                {'slug': 'accessibility', 'name': 'accessibility'},
                {'slug': 'training', 'name': 'training'},
                {'slug': 'drivers', 'name': 'drivers'},
            ]
            
            for tag_data in tags_data:
                tag, created = Tag.objects.get_or_create(
                    slug=tag_data['slug'],
                    defaults={
                        'name': tag_data['name'],
                    }
                )
                tags_map[tag_data['slug']] = tag
                status = 'Created' if created else 'Already exists'
                self.stdout.write(f'  {status}: {tag.name}')
            
            # Step 3: Create FAQs
            self.stdout.write('\n3. Creating FAQs...')
            faqs_created = 0
            faqs_updated = 0
            
            faqs_data = [
                {
                    'question': 'How do I report a late or missed bus operated by the ministry?',
                    'answer': 'You can report late or missed buses through the Transport Service Ministry mobile app, the web portal, or by calling the contact centre. Please provide the route number, bus registration (if visible), stop name, direction of travel and approximate time. This information allows the Route Operations team to check vehicle tracking logs and address the issue with the operating depot.',
                    'category_slug': 'customer-service-complaints',
                    'tag_slugs': ['routes', 'complaints'],
                    'is_published': True,
                },
                {
                    'question': 'What discounts are available for students, seniors and persons with disabilities?',
                    'answer': 'The ministry offers concession fares for full-time students, registered seniors above the age threshold, and passengers with certified disabilities. To access these discounts, commuters must apply for a personalised smart card via the online portal or any designated service centre, and present the card when boarding or tapping in. The current concession rates and eligibility criteria are published on the ministry website and updated annually.',
                    'category_slug': 'ticketing-fares',
                    'tag_slugs': ['fares', 'accessibility'],
                    'is_published': True,
                },
                {
                    'question': 'How do I retrieve an item I left on a ministry bus?',
                    'answer': 'If you lose an item on a bus, report it within 24 hours through the mobile app or contact centre. Share the route number, direction, approximate time of travel, boarding and alighting stops, and a clear description of the item. Lost property is stored at the depot for a limited period; high-value items are logged and may require proof of ownership before collection.',
                    'category_slug': 'customer-service-complaints',
                    'tag_slugs': ['lost-and-found', 'routes'],
                    'is_published': True,
                },
                {
                    'question': 'What should I do if I witness unsafe driving by a ministry bus driver?',
                    'answer': 'If you observe speeding, harsh braking, use of mobile phones while driving or any other unsafe behaviour, please report it immediately through the hotline or mobile app emergency option. Provide the bus registration, route number, location, time and a brief description. Safety & Compliance will review CCTV and telematics data, and if the allegation is confirmed, appropriate disciplinary and retraining actions will be taken.',
                    'category_slug': 'safety-compliance',
                    'tag_slugs': ['safety', 'drivers'],
                    'is_published': True,
                },
                {
                    'question': 'Are ministry buses accessible to wheelchair users and parents with strollers?',
                    'answer': 'Most ministry-operated buses are low-floor and equipped with ramps, priority seating and reserved spaces for wheelchairs and strollers. If you require additional assistance, please inform the driver when boarding. In case an accessible bus is not available, our control centre can arrange the next closest accessible vehicle where operationally feasible.',
                    'category_slug': 'safety-compliance',
                    'tag_slugs': ['accessibility', 'safety'],
                    'is_published': True,
                },
                {
                    'question': 'Why do routes and timetables change during school holidays and major events?',
                    'answer': 'The ministry uses ridership data and demand forecasts to adjust services during school holidays, festivals and large events. Frequencies may be reduced on low-demand routes and increased on corridors serving event venues. All planned changes are published at least two weeks in advance on the ministry website, mobile app and at major stops.',
                    'category_slug': 'route-operations',
                    'tag_slugs': ['routes'],
                    'is_published': True,
                },
            ]
            
            for faq_data in faqs_data:
                category = categories_map.get(faq_data['category_slug']) if faq_data.get('category_slug') else None
                tag_objects = [tags_map[tag_slug] for tag_slug in faq_data.get('tag_slugs', []) if tag_slug in tags_map]
                
                faq, created = FAQ.objects.get_or_create(
                    question=faq_data['question'],
                    defaults={
                        'answer': faq_data['answer'],
                        'category': category,
                        'is_published': faq_data.get('is_published', False),
                        'view_count': 0,
                        'helpful_count': 0,
                        'not_helpful_count': 0,
                    }
                )
                
                if not created:
                    faq.answer = faq_data['answer']
                    faq.category = category
                    faq.is_published = faq_data.get('is_published', False)
                    faq.save()
                    faqs_updated += 1
                else:
                    faqs_created += 1
                
                faq.tags.set(tag_objects)
                status = 'Created' if created else 'Updated'
                self.stdout.write(f'  {status}: {faq.question[:50]}...')
            
            # Step 4: Create SOPs
            self.stdout.write('\n4. Creating SOPs...')
            sops_created = 0
            sops_updated = 0
            
            sops_data = [
                {
                    'title': 'SOP: Handling Customer Complaints on Transport Services',
                    'content': '1. Receive the complaint via phone, app, email or walk-in and register it in the CRM within 15 minutes of receipt.\n2. Classify the complaint (service quality, safety, staff behaviour, fare dispute, accessibility, other) and assign a priority level.\n3. Acknowledge the complaint to the commuter within one working day, providing a reference number and expected resolution timeline.\n4. Route the case to the responsible depot, route supervisor or Safety & Compliance unit based on the category.\n5. Investigate using CCTV footage, telematics data, driver statements and ticketing records where applicable.\n6. Propose corrective actions (staff coaching, disciplinary action, schedule adjustment, policy clarification) and record them in the CRM.\n7. Communicate the outcome clearly to the commuter and close the case once actions are implemented.',
                    'version': '1.0',
                    'category_slug': 'customer-service-complaints',
                    'tag_slugs': ['complaints'],
                    'status': 'approved',
                    'is_published': True,
                },
                {
                    'title': 'SOP: Bus Accident and Incident Reporting',
                    'content': '1. The driver must stop the vehicle safely, activate hazard lights and secure the scene following the Driver Safety Card.\n2. Immediately inform the control centre via radio or the emergency mobile channel, providing route, location, apparent injuries and damage.\n3. Control centre alerts emergency services, depot management and Safety & Compliance.\n4. The driver must not admit liability or make unofficial settlements with third parties.\n5. Collect passenger details where feasible and provide a standard information slip with the case reference.\n6. Complete the Accident Report Form within 24 hours and attend debriefing with the depot manager and safety officer.\n7. Safety & Compliance conducts a root cause analysis and recommends corrective and preventive actions.',
                    'version': '1.0',
                    'category_slug': 'safety-compliance',
                    'tag_slugs': ['safety', 'drivers'],
                    'status': 'approved',
                    'is_published': True,
                },
                {
                    'title': 'SOP: Daily Bus Pre-Trip Inspection',
                    'content': '1. Drivers must arrive at the depot at least 20 minutes before departure to complete the pre-trip inspection checklist.\n2. Inspect tyres, mirrors, lights, wipers, indicators, horn and doors for proper operation.\n3. Check fuel level, engine warning lights and ensure no fluid leaks are visible under the vehicle.\n4. Verify that fire extinguishers, first-aid kits and emergency hammers are present and within validity.\n5. Confirm that ramp mechanisms and wheelchair securement equipment are functional.\n6. Record findings in the electronic inspection form and report critical defects to maintenance immediately.\n7. Vehicles with safety-critical defects must not be dispatched until cleared by maintenance.',
                    'version': '1.0',
                    'category_slug': 'fleet-maintenance',
                    'tag_slugs': ['safety', 'drivers'],
                    'status': 'approved',
                    'is_published': True,
                },
            ]
            
            for sop_data in sops_data:
                category = categories_map.get(sop_data['category_slug']) if sop_data.get('category_slug') else None
                tag_objects = [tags_map[tag_slug] for tag_slug in sop_data.get('tag_slugs', []) if tag_slug in tags_map]
                
                sop, created = SOP.objects.get_or_create(
                    title=sop_data['title'],
                    defaults={
                        'content': sop_data['content'],
                        'version': sop_data.get('version', '1.0'),
                        'category': category,
                        'status': sop_data.get('status', 'draft'),
                        'is_published': sop_data.get('is_published', False),
                        'view_count': 0,
                    }
                )
                
                if not created:
                    sop.content = sop_data['content']
                    sop.version = sop_data.get('version', '1.0')
                    sop.category = category
                    sop.status = sop_data.get('status', 'draft')
                    sop.is_published = sop_data.get('is_published', False)
                    sop.save()
                    sops_updated += 1
                else:
                    sops_created += 1
                
                sop.tags.set(tag_objects)
                status = 'Created' if created else 'Updated'
                self.stdout.write(f'  {status}: {sop.title[:50]}...')
            
            # Step 5: Create Policy Explanations
            self.stdout.write('\n5. Creating Policy Explanations...')
            policies_created = 0
            policies_updated = 0
            
            policies_data = [
                {
                    'title': 'Public Transport Service Quality Standards',
                    'content': 'The Transport Service Ministry has adopted service quality standards covering punctuality, vehicle cleanliness, accessibility and customer service. Key metrics include on-time performance, missed trips, complaint response times and vehicle condition ratings. Operators are required to meet minimum thresholds under their operating contracts, and persistent under-performance can trigger penalty points or contract review. This policy explains how performance is measured, how data is validated and how commuters can access published performance reports.',
                    'policy_reference': 'TSM-SVC-001',
                    'category_slug': 'route-operations',
                    'tag_slugs': ['routes'],
                    'is_published': True,
                },
                {
                    'title': 'Concession Fare and Subsidy Policy',
                    'content': 'The concession fare and subsidy policy defines who qualifies for reduced public transport fares and how subsidies are funded. Eligibility currently includes full-time students, seniors and persons with disabilities, subject to verification through partner agencies. The ministry reimburses operators for the difference between full and concession fares based on validated ticketing data. This document explains the application process, renewal requirements and how changes are communicated to the public.',
                    'policy_reference': 'TSM-FARE-003',
                    'category_slug': 'ticketing-fares',
                    'tag_slugs': ['fares', 'accessibility'],
                    'is_published': True,
                },
                {
                    'title': 'Driver Conduct and Disciplinary Policy',
                    'content': 'This policy sets expectations for professional behaviour by ministry and contracted bus drivers, including safe driving, respectful communication and zero tolerance for harassment or discrimination. It outlines how complaints are investigated, the range of possible outcomes (coaching, warnings, suspension, termination) and the driver appeal process. The policy is aligned with national labour laws and road safety regulations and is communicated to all drivers during induction and refresher training.',
                    'policy_reference': 'TSM-HR-009',
                    'category_slug': 'safety-compliance',
                    'tag_slugs': ['safety', 'drivers'],
                    'is_published': True,
                },
            ]
            
            for policy_data in policies_data:
                category = categories_map.get(policy_data['category_slug']) if policy_data.get('category_slug') else None
                tag_objects = [tags_map[tag_slug] for tag_slug in policy_data.get('tag_slugs', []) if tag_slug in tags_map]
                
                policy, created = PolicyExplanation.objects.get_or_create(
                    title=policy_data['title'],
                    defaults={
                        'content': policy_data['content'],
                        'policy_reference': policy_data.get('policy_reference', ''),
                        'category': category,
                        'is_published': policy_data.get('is_published', False),
                        'view_count': 0,
                    }
                )
                
                if not created:
                    policy.content = policy_data['content']
                    policy.policy_reference = policy_data.get('policy_reference', '')
                    policy.category = category
                    policy.is_published = policy_data.get('is_published', False)
                    policy.save()
                    policies_updated += 1
                else:
                    policies_created += 1
                
                policy.tags.set(tag_objects)
                status = 'Created' if created else 'Updated'
                self.stdout.write(f'  {status}: {policy.title[:50]}...')
            
            # Step 6: Create Training Articles
            self.stdout.write('\n6. Creating Training Articles...')
            articles_created = 0
            articles_updated = 0
            
            articles_data = [
                {
                    'title': 'Introduction to the Transport Service Ministry Network',
                    'content': 'This module gives new staff an overview of the Transport Service Ministry\'s mandate, governance structure and service network. It explains the difference between trunk, feeder and express routes, as well as the roles of the control centre, depots and contracted operators. Staff will learn how service levels are planned, how performance is monitored and how front-line feedback flows back into planning decisions.',
                    'summary': 'Overview of the ministry\'s public transport network and operating model for new staff.',
                    'category_slug': 'route-operations',
                    'tag_slugs': ['training'],
                    'difficulty_level': 'beginner',
                    'estimated_read_time': 10,
                    'is_published': True,
                },
                {
                    'title': 'Customer Service Fundamentals for Bus Conductors and Drivers',
                    'content': 'This article covers the basics of customer service in a public transport context: greeting passengers, giving clear announcements, handling inquiries and managing difficult interactions calmly. It includes practical scenarios such as overcrowded buses, timetable disruptions and complaints about fares. Staff are encouraged to use the LEARN model (Listen, Empathise, Apologise, Resolve, Notify) when handling complaints and to record serious incidents in the CRM.',
                    'summary': 'Foundational customer service skills tailored for front-line transport staff.',
                    'category_slug': 'customer-service-complaints',
                    'tag_slugs': ['complaints', 'training'],
                    'difficulty_level': 'beginner',
                    'estimated_read_time': 12,
                    'is_published': True,
                },
                {
                    'title': 'Road Safety and Defensive Driving for Public Transport',
                    'content': 'This module introduces defensive driving principles for urban bus operations, including hazard perception, maintaining safe following distances and managing blind spots. It explains how telematics data is used to monitor harsh braking, rapid acceleration and speeding, and how these indicators feed into coaching sessions. Drivers will review key national road rules that apply to public service vehicles and learn techniques for driving smoothly to improve passenger comfort and safety.',
                    'summary': 'Core road safety and defensive driving concepts for ministry and contracted drivers.',
                    'category_slug': 'safety-compliance',
                    'tag_slugs': ['safety', 'drivers'],
                    'difficulty_level': 'intermediate',
                    'estimated_read_time': 15,
                    'is_published': True,
                },
                {
                    'title': 'Serving Passengers with Disabilities and Special Needs',
                    'content': 'This article helps staff understand different types of disabilities and how they may affect a passenger\'s journey. It provides guidance on operating ramps, communicating with visually or hearing-impaired passengers and making reasonable accommodations. Emphasis is placed on dignity, patience and clear communication, as well as on the ministry\'s legal obligations under accessibility legislation.',
                    'summary': 'Practical guidance for safely and respectfully serving passengers with disabilities.',
                    'category_slug': 'safety-compliance',
                    'tag_slugs': ['accessibility', 'training'],
                    'difficulty_level': 'intermediate',
                    'estimated_read_time': 14,
                    'is_published': True,
                },
                {
                    'title': 'Using the Ministry CRM and Mobile Tools on the Road',
                    'content': 'Front-line staff increasingly interact with the ministry\'s digital tools, including the CRM mobile app and driver tablets. This module explains how to log incidents, update trip status and escalate urgent issues from the field. It also covers data privacy basics and the importance of accurate, neutral descriptions when recording customer complaints or incidents.',
                    'summary': 'How to use the CRM and mobile applications effectively and securely while on duty.',
                    'category_slug': 'digital-channels-e-ticketing',
                    'tag_slugs': ['training'],
                    'difficulty_level': 'intermediate',
                    'estimated_read_time': 12,
                    'is_published': True,
                },
                {
                    'title': 'Basics of Fleet Maintenance for Operations Staff',
                    'content': 'While maintenance technicians handle repairs, operations staff must understand the basics of fleet condition and defect reporting. This article explains key components such as brakes, tyres and suspension in non-technical language, and describes when a bus must be withdrawn from service. Staff learn how to read basic maintenance dashboards and how to use defect codes consistently.',
                    'summary': 'Non-technical introduction to fleet maintenance concepts for operations personnel.',
                    'category_slug': 'fleet-maintenance',
                    'tag_slugs': ['safety', 'training'],
                    'difficulty_level': 'beginner',
                    'estimated_read_time': 11,
                    'is_published': True,
                },
                {
                    'title': 'Planning and Communicating Service Changes',
                    'content': 'This training article is aimed at planners and communications officers. It explains the end-to-end process for planning service changes: analysing ridership data, drafting proposals, consulting stakeholders and obtaining approvals. It also covers best practices for communicating changes to the public through stop posters, press releases, social media and the mobile app, with a focus on clear, commuter-friendly language.',
                    'summary': 'How to design and communicate route and timetable changes effectively.',
                    'category_slug': 'route-operations',
                    'tag_slugs': ['routes', 'training'],
                    'difficulty_level': 'advanced',
                    'estimated_read_time': 18,
                    'is_published': True,
                },
                {
                    'title': 'Managing Major Disruptions and Contingency Routes',
                    'content': 'Severe weather, road closures and large public events can disrupt normal services. This advanced module explains how the ministry activates contingency plans, including diversion routes, shuttle services and dynamic headway management. It introduces the roles of the disruption cell, real-time passenger information team and depot coordinators, and it highlights how consistent internal communication prevents conflicting messages to commuters.',
                    'summary': 'Advanced guide to handling major network disruptions and keeping passengers informed.',
                    'category_slug': 'route-operations',
                    'tag_slugs': ['routes', 'safety', 'training'],
                    'difficulty_level': 'advanced',
                    'estimated_read_time': 20,
                    'is_published': True,
                },
            ]
            
            for article_data in articles_data:
                category = categories_map.get(article_data['category_slug']) if article_data.get('category_slug') else None
                tag_objects = [tags_map[tag_slug] for tag_slug in article_data.get('tag_slugs', []) if tag_slug in tags_map]
                
                article, created = TrainingArticle.objects.get_or_create(
                    title=article_data['title'],
                    defaults={
                        'content': article_data['content'],
                        'summary': article_data.get('summary', ''),
                        'category': category,
                        'difficulty_level': article_data.get('difficulty_level', 'beginner'),
                        'estimated_read_time': article_data.get('estimated_read_time', 0),
                        'is_published': article_data.get('is_published', False),
                        'view_count': 0,
                    }
                )
                
                if not created:
                    article.content = article_data['content']
                    article.summary = article_data.get('summary', '')
                    article.category = category
                    article.difficulty_level = article_data.get('difficulty_level', 'beginner')
                    article.estimated_read_time = article_data.get('estimated_read_time', 0)
                    article.is_published = article_data.get('is_published', False)
                    article.save()
                    articles_updated += 1
                else:
                    articles_created += 1
                
                article.tags.set(tag_objects)
                status = 'Created' if created else 'Updated'
                self.stdout.write(f'  {status}: {article.title[:50]}...')
            
            # Summary
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✅ Successfully loaded data:\n'
                    f'  - {len(categories_map)} Categories\n'
                    f'  - {len(tags_map)} Tags\n'
                    f'  - {faqs_created} FAQs created, {faqs_updated} updated\n'
                    f'  - {sops_created} SOPs created, {sops_updated} updated\n'
                    f'  - {policies_created} Policy Explanations created, {policies_updated} updated\n'
                    f'  - {articles_created} Training Articles created, {articles_updated} updated'
                )
            )
