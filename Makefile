##
## You provide this to build your docker image
##

build: buildRestLogs buildWorker

buildRestLogs:
	(cd rest; make build)

buildWorker:
	(cd worker; make build)

push: pushRestLogs pushWorker

pushRestLogs:
	(cd rest; make push)

pushWorker:
	(cd worker; make push)

run: runRestLogs runWorker

runRestLogs:
	(cd rest; make run)

runWorker:
	(cd worker; make run)

localDeploy:
	kubectl apply -f redis/redis-deployment.yaml
	kubectl apply -f redis/redis-service.yaml
	kubectl apply -f rabbitmq/rabbitmq-deployment.yaml
	kubectl apply -f rabbitmq/rabbitmq-service.yaml

	sleep 5
	kubectl port-forward --address 0.0.0.0 service/rabbitmq 5672:5672 &
	kubectl port-forward --address 0.0.0.0 service/redis 6379:6379 &
	sleep 5

	kubectl apply -f rest/rest-deployment.yaml
	kubectl apply -f rest/rest-service.yaml
	kubectl apply -f rest/rest-ingress.yaml
	sleep 5
	kubectl port-forward --address 0.0.0.0 service/rest-service 5000:5000 &
	sleep 5
	
	kubectl apply -f rest/logs-deployment.yaml

	kubectl apply -f worker/worker-deployment.yaml
	
	(cd rabitmq; kubectl apply -f servicemonitor-rabbitmq.yaml)
	(cd rabbitmq; kubectl apply -f rabbitmq-scaling-rules.yaml)
	(cd rabbitmq; kubectl apply -f rabbitmq-scaling-hpa.yaml)

	kubectl port-forward service/my-prom-grafana 9999:80 &

localClean:
	kubectl delete deployment redis
	kubectl delete deployment rabbitmq
	kubectl delete service redis
	kubectl delete service rabbitmq

	-@pkill -f port-forwardma

runKube:
	kubectl apply -f redis/redis-deployment.yaml
	kubectl apply -f redis/redis-service.yaml
	kubectl apply -f rabbitmq/rabbitmq-deployment.yaml
	kubectl apply -f rabbitmq/rabbitmq-service.yaml

	sleep 5

	(cd rest; make runKube)
	(cd worker; make runKube)

clean:
	kubectl delete deployment redis
	kubectl delete deployment rabbitmq
	kubectl delete service redis
	kubectl delete service rabbitmq

	(cd rest; make cleanKube)
	(cd worker; make cleanKube)

default: build